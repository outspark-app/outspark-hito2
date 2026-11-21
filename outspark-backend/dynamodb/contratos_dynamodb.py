"""Contratos de persistencia v2. Referencia ejecutable, sin API ni autenticación.

La integración local ejercita TransactWriteItems con el SDK real. El actor que aquí
recibe cada función deberá provenir del JWT verificado en la futura Lambda.
"""
import hashlib
import json
import re
from uuid import uuid4
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from botocore.exceptions import ClientError

SER, DES = TypeSerializer(), TypeDeserializer()
MAX_SNAPSHOT_BYTES = 128 * 1024
IDENTIFIER = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def encode(item):
    return {key: SER.serialize(value) for key, value in item.items()}


def decode(item):
    return {key: DES.deserialize(value) for key, value in item.items()}


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Identificador inválido')
    return value


def event_key(ref):
    if not isinstance(ref, str) or ref.count('/') != 1:
        raise ValueError('Referencia de evento inválida')
    post, event = map(identifier, ref.split('/'))
    return {'PK': f'POST#{post}', 'SK': f'EVENT#{event}'}


def digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def get(client, table, pk, sk):
    item = client.get_item(TableName=table, Key=encode({'PK': pk, 'SK': sk}),
                           ConsistentRead=True).get('Item')
    return decode(item) if item else None


def query(client, table, pk, prefix):
    """Query paginada sobre tabla base, con lectura fuerte. No hace Scan."""
    args = dict(TableName=table, KeyConditionExpression='PK = :pk AND begins_with(SK, :prefix)',
                ExpressionAttributeValues=encode({':pk': pk, ':prefix': prefix}),
                ConsistentRead=True)
    result = []
    while True:
        page = client.query(**args)
        result.extend(decode(item) for item in page['Items'])
        if 'LastEvaluatedKey' not in page:
            return result
        args['ExclusiveStartKey'] = page['LastEvaluatedKey']


def put(table, item):
    return {'Put': {'TableName': table, 'Item': encode(item),
                    'ConditionExpression': 'attribute_not_exists(PK)'}}


def check(table, key, condition, values=None, names=None):
    result = {'TableName': table, 'Key': encode(key), 'ConditionExpression': condition}
    if values:
        result['ExpressionAttributeValues'] = encode(values)
    if names:
        result['ExpressionAttributeNames'] = names
    return {'ConditionCheck': result}


def validate_transaction(actions):
    if not 1 <= len(actions) <= 100:
        raise ValueError('Una transacción admite 1–100 acciones')
    seen = set()
    for action in actions:
        op = next(iter(action.values()))
        item = decode(op.get('Item', op.get('Key')))
        key = (op['TableName'], item['PK'], item['SK'])
        if key in seen:
            raise ValueError('Dos acciones sobre el mismo ítem')
        seen.add(key)
    # Conservative JSON serialization bound, not an exact billing-size calculator.
    if len(json.dumps(actions, ensure_ascii=False).encode()) > 4 * 1024 * 1024:
        raise ValueError('Transacción demasiado grande')


def commit(client, actions):
    validate_transaction(actions)
    client.transact_write_items(TransactItems=actions)


def request_record(client, table, actor, request_key, payload):
    identifier(actor)
    profile = get(client, table, f'USER#{actor}', 'PROFILE')
    if not profile or profile.get('status') != 'ACTIVE':
        raise PermissionError('Cuenta inactiva o inexistente')
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Clave de idempotencia inválida')
    key = {'PK': f'USER#{actor}', 'SK': f'REQUEST#{hashlib.sha256(request_key.encode()).hexdigest()}'}
    record = get(client, table, **{'pk': key['PK'], 'sk': key['SK']})
    fingerprint = digest(payload)
    if record and record['payload_hash'] != fingerprint:
        raise ValueError('Clave de idempotencia reutilizada para otra operación')
    return key, fingerprint, record


def commit_request(client, table, actions, key, fingerprint, result):
    try:
        commit(client, actions)
    except ClientError as error:
        # Dos peticiones concurrentes pueden leer la ausencia del mismo REQUEST.
        # Recuperar el resultado confirmado; otros conflictos siguen siendo errores.
        if error.response['Error']['Code'] != 'TransactionCanceledException':
            raise
        saved = get(client, table, key['PK'], key['SK'])
        if not saved or saved['payload_hash'] != fingerprint:
            raise
        return saved['result'], []
    return result, actions


def user_check(table, actor):
    return check(table, {'PK': f'USER#{actor}', 'SK': 'PROFILE'},
                 'attribute_exists(PK) AND #state = :active', {':active': 'ACTIVE'}, {'#state': 'status'})


def publish(client, table, actor, community, body, topic_ids, request_key, created_at):
    identifier(community)
    if not isinstance(body, str) or not 1 <= len(body.strip()) <= 1000:
        raise ValueError('Texto de 1–1000 caracteres')
    if not 1 <= len(topic_ids) <= 3 or len(set(topic_ids)) != len(topic_ids):
        raise ValueError('De 1 a 3 temas distintos')
    for topic in topic_ids:
        identifier(topic)
    body = body.strip()
    payload = {'operation': 'publish', 'community_id': community, 'body': body, 'topic_ids': sorted(topic_ids)}
    key, fingerprint, old = request_record(client, table, actor, request_key, payload)
    if old:
        return old['result'], []
    post_id, event_part = str(uuid4()), str(uuid4())
    ref = f'{post_id}/{event_part}'
    result = {'publication_id': post_id, 'event_id': ref}
    actions = [user_check(table, actor),
               check(table, {'PK': f'COMM#{community}', 'SK': 'META'}, '#state = :active',
                     {':active': 'ACTIVE'}, {'#state': 'status'}),
               check(table, {'PK': f'USER#{actor}', 'SK': f'MEMBER#{community}'}, '#state = :active',
                     {':active': 'ACTIVE'}, {'#state': 'status'})]
    actions += [check(table, {'PK': 'CATALOG#TOPIC', 'SK': f'TOPIC#{t}'},
                      'attribute_exists(PK)') for t in topic_ids]
    original = dict(PK=f'POST#{post_id}', SK='META', entity_type='PUBLICATION',
                    publication_id=post_id, author_id=actor, community_id=community,
                    body=body, topic_ids=sorted(topic_ids), visibility='public', status='ACTIVE',
                    root_event_id=ref, created_at=created_at,
                    GSI2PK=f'COMM#{community}', GSI2SK=f'{created_at}#{post_id}')
    root = dict(PK=f'POST#{post_id}', SK=f'EVENT#{event_part}', entity_type='EVENT',
                publication_id=post_id, actor_id=actor, parent_event_id=None, event_id=ref,
                created_at=created_at, GSI1PK=f'ACTOR#{actor}', GSI1SK=f'{created_at}#{ref}')
    actions += [put(table, original), put(table, root),
                put(table, dict(PK=f'POST#{post_id}', SK=f'ACTOR#{actor}', entity_type='PARTICIPATION', event_id=ref)),
                put(table, dict(**key, entity_type='REQUEST', payload_hash=fingerprint,
                                result=result, created_at=created_at))]
    return commit_request(client, table, actions, key, fingerprint, result)


def repost(client, table, actor, parent_ref, request_key, created_at):
    key, fingerprint, old = request_record(client, table, actor, request_key,
                                           {'operation': 'repost', 'parent_event_id': parent_ref})
    if old:
        return old['result'], []
    parent_key = event_key(parent_ref)
    parent = get(client, table, parent_key['PK'], parent_key['SK'])
    if not parent or parent.get('entity_type') != 'EVENT':
        raise ValueError('Padre inexistente')
    post_id = identifier(parent['publication_id'])
    if parent_key['PK'] != f'POST#{post_id}' or parent.get('event_id') != parent_ref:
        raise ValueError('Padre corrupto o de otro original')
    original = get(client, table, f'POST#{post_id}', 'META')
    if not original:
        raise ValueError('Original inexistente')
    event_part = str(uuid4())
    ref = f'{post_id}/{event_part}'
    result = {'publication_id': post_id, 'event_id': ref}
    event = dict(PK=f'POST#{post_id}', SK=f'EVENT#{event_part}', entity_type='EVENT',
                 publication_id=post_id, actor_id=actor, parent_event_id=parent_ref, event_id=ref,
                 created_at=created_at, GSI1PK=f'ACTOR#{actor}', GSI1SK=f'{created_at}#{ref}')
    actions = [user_check(table, actor),
               check(table, {'PK': f'POST#{post_id}', 'SK': 'META'}, '#state = :active AND visibility = :public',
                     {':active': 'ACTIVE', ':public': 'public'}, {'#state': 'status'}),
               check(table, parent_key, 'publication_id = :post AND event_id = :parent',
                     {':post': post_id, ':parent': parent_ref}),
               put(table, event),
               put(table, dict(PK=f'POST#{post_id}', SK=f'ACTOR#{actor}', entity_type='PARTICIPATION', event_id=ref)),
               put(table, dict(**key, entity_type='REQUEST', payload_hash=fingerprint,
                               result=result, created_at=created_at))]
    return commit_request(client, table, actions, key, fingerprint, result)


def routes(events, sources, root_ref):
    lookup = {e['event_id']: e for e in events}
    expected_pk = event_key(root_ref)['PK']
    paths = []
    for source in sources:
        current, seen, path = source, set(), []
        while current is not None:
            if current in seen:
                raise ValueError('Ciclo en datos de procedencia')
            if current not in lookup:
                raise ValueError('Padre ausente al leer procedencia')
            seen.add(current)
            e = lookup[current]
            if event_key(current)['PK'] != expected_pk or expected_pk != f"POST#{e['publication_id']}":
                raise ValueError('Referencia cruzada de contenido')
            path.append(e)
            current = e['parent_event_id']
        if path[-1]['event_id'] != root_ref:
            raise ValueError('Raíz diferente de la registrada')
        paths.append(list(reversed(path)))
    return paths


def snapshot(client, table, viewer, cards, generated_at, snapshot_id=None, strategy='chronological',
             selection=None, event_loader=None):
    """Persiste un snapshot cerrado y protege motivos observados en el commit.

    Entrada ya seleccionada por el feed: 0–10 tarjetas, <=200 eventos fuente,
    <=20 contactos y <=10 comunidades. Conserva razones por fuente sin truncar.
    """
    identifier(viewer)
    if strategy not in ('chronological', 'diverse'):
        raise ValueError('Estrategia inválida')
    if not 0 <= len(cards) <= 10:
        raise ValueError('De 0 a 10 tarjetas en este contrato de prueba')
    if len({c['publication_id'] for c in cards}) != len(cards):
        raise ValueError('Original duplicado')
    guards, contacts, communities = {}, set(), set()
    source_count = 0
    for position, card in enumerate(cards):
        post_id = identifier(card['publication_id'])
        if card.get('position') != position:
            raise ValueError('Posición de tarjeta inválida')
        original = get(client, table, f'POST#{post_id}', 'META')
        if not original:
            raise ValueError('Original inexistente')
        sources = card['sources']
        if not sources or len({s['event_id'] for s in sources}) != len(sources):
            raise ValueError('Fuentes vacías o duplicadas')
        source_count += len(sources)
        events = event_loader(post_id) if event_loader else query(client, table, f'POST#{post_id}', 'EVENT#')
        paths = routes(events, [s['event_id'] for s in sources], original['root_event_id'])
        guard_key = (f'POST#{post_id}', 'META')
        guards[guard_key] = check(table, dict(PK=guard_key[0], SK=guard_key[1]), '#state = :active',
                                  {':active': 'ACTIVE'}, {'#state': 'status'})
        for source, path in zip(sources, paths):
            if any(e['publication_id'] != post_id for e in path):
                raise ValueError('Fuente de otro original')
            actor = path[-1]['actor_id']
            reasons = source['reasons']
            if not reasons or len(reasons) > 4 or len({r['type'] for r in reasons}) != len(reasons):
                raise ValueError('Razones vacías o repetidas')
            for reason in reasons:
                if not 1 <= len(reason.get('text', '')) <= 160:
                    raise ValueError('Texto de razón inválido')
                kind = reason['type']
                if kind == 'contact':
                    if reason.get('contact_id') != actor or actor == viewer:
                        raise ValueError('Contacto no corresponde al evento fuente')
                    contacts.add(actor)
                    gk = (f'USER#{viewer}', f'CONTACT#{actor}')
                    guards[gk] = check(table, dict(PK=gk[0], SK=gk[1]), '#state = :active',
                                       {':active': 'ACTIVE'}, {'#state': 'status'})
                elif kind == 'community':
                    cid = reason.get('community_id')
                    if cid != original['community_id']:
                        raise ValueError('Comunidad no corresponde al original')
                    communities.add(cid)
                    gk = (f'USER#{viewer}', f'MEMBER#{cid}')
                    guards[gk] = check(table, dict(PK=gk[0], SK=gk[1]), '#state = :active',
                                       {':active': 'ACTIVE'}, {'#state': 'status'})
                elif kind == 'own':
                    if original['author_id'] != viewer:
                        raise ValueError('Publicación propia atribuida a otra cuenta')
                elif kind == 'discovery':
                    # Design policy: all v1 discovery is public community content,
                    # selected under the recorded algorithm version; it need not match a topic.
                    if original['visibility'] != 'public':
                        raise ValueError('Descubrimiento no público')
                else:
                    raise ValueError('Tipo de razón desconocido')
    if source_count > 200 or len(contacts) > 20 or len(communities) > 10:
        raise ValueError('Se excedió el alcance acotado del feed')
    sid = identifier(snapshot_id or str(uuid4()))
    item = dict(PK=f'FEED#{sid}', SK='META', entity_type='FEED_SNAPSHOT', snapshot_id=sid,
                viewer_id=viewer, strategy=strategy, algorithm_version='feed-v1',
                generated_at=generated_at, cards=cards, source_count=source_count,
                limits={'candidates': 200, 'cards': 10, 'contacts': 20, 'communities': 10})
    if selection is not None:
        item['selection'] = selection
    if len(json.dumps(item, ensure_ascii=False, separators=(',', ':')).encode()) > MAX_SNAPSHOT_BYTES:
        raise ValueError('Snapshot excede límite interno de 128 KiB')
    pointer = dict(PK=f'USER#{viewer}', SK=f'FEED#{generated_at}#{sid}',
                   entity_type='FEED_POINTER', snapshot_id=sid, generated_at=generated_at)
    actions = [user_check(table, viewer), *guards.values(), put(table, item), put(table, pointer)]
    commit(client, actions)
    return sid, actions


def read_snapshot(client, table, viewer, snapshot_id):
    item = get(client, table, f'FEED#{identifier(snapshot_id)}', 'META')
    if not item:
        raise ValueError('Snapshot inexistente')
    if item['viewer_id'] != viewer:
        raise PermissionError('Snapshot de otra cuenta')
    return item
