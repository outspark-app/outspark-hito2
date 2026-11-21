"""Integración real con DynamoDB Local; nunca escribe en AWS."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
import boto3
from botocore.exceptions import ClientError
import contratos_dynamodb as domain

BASE = Path(__file__).resolve().parent
NOW = '2026-10-12T15:00:00.000Z'
checks, examples = [], {}


def verify(name, function):
    function()
    checks.append({'caso': name, 'resultado': 'PASS'})


def assert_equal(actual, expected):
    assert actual == expected, (actual, expected)


def rejected(function, exceptions=(ValueError, PermissionError, ClientError)):
    try:
        function()
    except exceptions:
        return
    raise AssertionError('Operación inválida aceptada')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default='http://127.0.0.1:18000')
    args = parser.parse_args()
    parsed = urlparse(args.endpoint)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise SystemExit('Solo se admite DynamoDB Local en loopback')
    client = boto3.client('dynamodb', endpoint_url=args.endpoint, region_name='us-east-1',
                          aws_access_key_id='outsparkLocal', aws_secret_access_key='outsparkLocal')
    config = json.loads((BASE / 'tabla_dynamodb.json').read_text())
    table = 'Outspark-test-' + uuid4().hex
    config['TableName'] = table
    created = False
    try:
        client.create_table(**config)
        created = True
        client.get_waiter('table_exists').wait(TableName=table)

        def seed(item):
            client.put_item(TableName=table, Item=domain.encode(item))

        for uid in ('ana', 'bruno', 'carla', 'diego', 'elena'):
            seed(dict(PK=f'USER#{uid}', SK='PROFILE', entity_type='USER', status='ACTIVE', is_demo=True))
        seed(dict(PK='COMM#diseno', SK='META', entity_type='COMMUNITY', name='Diseño', status='ACTIVE'))
        seed(dict(PK='CATALOG#TOPIC', SK='TOPIC#diseno', entity_type='TOPIC', name='Diseño'))
        for uid in ('ana', 'diego'):
            for pk, sk in ((f'USER#{uid}', 'MEMBER#diseno'), ('COMM#diseno', f'MEMBER#{uid}')):
                seed(dict(PK=pk, SK=sk, entity_type='MEMBERSHIP', status='ACTIVE'))
        for uid in ('bruno', 'carla'):
            lo, hi = sorted(('diego', uid))
            for pk, sk in ((f'FRIEND#{lo}#{hi}', 'META'), ('USER#diego', f'CONTACT#{uid}'), (f'USER#{uid}', 'CONTACT#diego')):
                seed(dict(PK=pk, SK=sk, entity_type='FRIENDSHIP', status='ACTIVE'))

        pub, tx = domain.publish(client, table, 'ana', 'diseno', 'Una idea conecta comunidades.', ['diseno'], 'publish-1', NOW)
        examples['publicar'] = {'resultado': pub, 'TransactItems': tx}
        pid, root = pub['publication_id'], pub['event_id']
        events = lambda: domain.query(client, table, f'POST#{pid}', 'EVENT#')
        original = lambda: domain.get(client, table, f'POST#{pid}', 'META')
        verify('Publicar crea original, raíz y bloqueo de autor atómicos',
               lambda: assert_equal((original()['root_event_id'], len(events()), domain.get(client, table, f'POST#{pid}', 'ACTOR#ana')['event_id']), (root, 1, root)))
        verify('Reintento de publicación devuelve el mismo resultado', lambda: assert_equal(
            domain.publish(client, table, 'ana', 'diseno', 'Una idea conecta comunidades.', ['diseno'], 'publish-1', NOW)[0], pub))
        verify('Idempotencia rechaza una misma clave con otro contenido', lambda: rejected(
            lambda: domain.publish(client, table, 'ana', 'diseno', 'Cambio de texto', ['diseno'], 'publish-1', NOW)))
        verify('Publicar sin pertenencia no escribe', lambda: rejected(
            lambda: domain.publish(client, table, 'bruno', 'diseno', 'Sin permiso', ['diseno'], 'invalid-membership', NOW)))
        verify('Publicar con tema inexistente no escribe', lambda: rejected(
            lambda: domain.publish(client, table, 'ana', 'diseno', 'Tema inválido', ['otro'], 'invalid-topic', NOW)))
        verify('Bloqueo de autor impide republicar su propio original', lambda: rejected(
            lambda: domain.repost(client, table, 'ana', root, 'own-repost', NOW)))
        b, tx = domain.repost(client, table, 'bruno', root, 'repost-1', NOW)
        examples['republicar'] = {'resultado': b, 'TransactItems': tx}
        c, _ = domain.repost(client, table, 'carla', b['event_id'], 'repost-1', NOW)
        verify('Republicación deriva el original del padre', lambda: assert_equal(c['publication_id'], pid))
        verify('Segunda republicación del mismo actor/original falla', lambda: rejected(
            lambda: domain.repost(client, table, 'bruno', c['event_id'], 'repost-2', NOW)))
        verify('Reintento de republicación no añade eventos', lambda: assert_equal(
            (domain.repost(client, table, 'bruno', root, 'repost-1', NOW)[0], len(events())), (b, 3)))
        verify('La clave de idempotencia distingue operaciones', lambda: rejected(
            lambda: domain.repost(client, table, 'ana', root, 'publish-1', NOW)))
        verify('Padre inexistente se rechaza', lambda: rejected(
            lambda: domain.repost(client, table, 'elena', f'{pid}/ausente', 'missing-parent', NOW)))
        verify('Referencias mal formadas se rechazan', lambda: rejected(lambda: domain.event_key('a/b/c')))
        paths = domain.routes(events(), [b['event_id'], c['event_id']], root)
        verify('Las dos llegadas conservan rutas Ana→Bruno y Ana→Bruno→Carla', lambda: assert_equal(
            [[e['actor_id'] for e in path] for path in paths], [['ana', 'bruno'], ['ana', 'bruno', 'carla']]))
        corrupt = deepcopy(events())
        next(e for e in corrupt if e['event_id'] == b['event_id'])['parent_event_id'] = c['event_id']
        verify('Lectura defensiva detecta ciclos', lambda: rejected(lambda: domain.routes(corrupt, [c['event_id']], root)))
        verify('Lectura defensiva detecta padres ausentes', lambda: rejected(
            lambda: domain.routes([e for e in events() if e['event_id'] != b['event_id']], [c['event_id']], root)))
        other = dict(event_id='otro/evento', publication_id='otro', actor_id='elena', parent_event_id=root)
        verify('Lectura defensiva detecta cruce de originales', lambda: rejected(
            lambda: domain.routes(events() + [other], ['otro/evento'], root)))

        def source(ref, actor):
            return {'event_id': ref, 'reasons': [
                {'type': 'contact', 'contact_id': actor, 'text': f'{actor} lo republicó.'},
                {'type': 'community', 'community_id': 'diseno', 'text': 'Sigues Diseño.'}]}
        cards = [{'publication_id': pid, 'position': 0, 'sources': [source(b['event_id'], 'bruno'), source(c['event_id'], 'carla')]}]
        sid, tx = domain.snapshot(client, table, 'diego', cards, NOW)
        examples['snapshot'] = {'snapshot_id': sid, 'TransactItems': tx}
        verify('Snapshot agrupa un original con dos fuentes y sus razones', lambda: assert_equal(
            (len(domain.read_snapshot(client, table, 'diego', sid)['cards']), domain.read_snapshot(client, table, 'diego', sid)['source_count']), (1, 2)))
        verify('Snapshot de otro destinatario no es consultable', lambda: rejected(
            lambda: domain.read_snapshot(client, table, 'ana', sid)))
        verify('Un snapshot cerrado no se sobrescribe', lambda: rejected(
            lambda: domain.snapshot(client, table, 'diego', cards, NOW, snapshot_id=sid)))
        verify('Un original no aparece dos veces en el snapshot', lambda: rejected(
            lambda: domain.snapshot(client, table, 'diego', cards + cards, NOW)))
        invalid = deepcopy(cards)
        invalid[0]['sources'][0]['reasons'][0]['contact_id'] = 'elena'
        verify('La razón de contacto debe corresponder al evento', lambda: rejected(
            lambda: domain.snapshot(client, table, 'diego', invalid, NOW)))
        invalid = deepcopy(cards)
        invalid[0]['sources'].append(deepcopy(invalid[0]['sources'][0]))
        verify('Una fuente no se duplica por tener varios motivos', lambda: rejected(
            lambda: domain.snapshot(client, table, 'diego', invalid, NOW)))
        empty_sid, _ = domain.snapshot(client, table, 'elena', [], NOW)
        verify('Feed vacío válido se puede guardar', lambda: assert_equal(
            domain.read_snapshot(client, table, 'elena', empty_sid)['cards'], []))

        # Simula una eliminación entre preparación de la transacción y su commit.
        pending = deepcopy(tx)
        oldsid = sid
        newsid = str(uuid4())
        for action in pending:
            if 'Put' in action:
                item = domain.decode(action['Put']['Item'])
                if item['entity_type'] == 'FEED_SNAPSHOT':
                    item['PK'], item['snapshot_id'] = f'FEED#{newsid}', newsid
                else:
                    item['SK'], item['snapshot_id'] = f'FEED#{NOW}#{newsid}', newsid
                action['Put']['Item'] = domain.encode(item)
        def remove_contact():
            lo, hi = sorted(('diego', 'bruno'))
            actions = []
            for pk, sk in ((f'FRIEND#{lo}#{hi}', 'META'), ('USER#diego', 'CONTACT#bruno'), ('USER#bruno', 'CONTACT#diego')):
                actions.append({'Update': {'TableName': table, 'Key': domain.encode({'PK': pk, 'SK': sk}),
                    'UpdateExpression': 'SET #state = :removed', 'ConditionExpression': '#state = :active',
                    'ExpressionAttributeNames': {'#state': 'status'},
                    'ExpressionAttributeValues': domain.encode({':removed': 'REMOVED', ':active': 'ACTIVE'})}})
            domain.commit(client, actions)
        verify('Retirar amistad actualiza el par y ambos espejos', lambda: (remove_contact(), assert_equal(
            domain.get(client, table, 'USER#bruno', 'CONTACT#diego')['status'], 'REMOVED')))
        verify('Contacto retirado impide confirmar el snapshot preparado', lambda: rejected(lambda: domain.commit(client, pending)))
        verify('Fallo de condición revierte snapshot y puntero completos', lambda: assert_equal(
            (domain.get(client, table, f'FEED#{newsid}', 'META'), domain.get(client, table, 'USER#diego', f'FEED#{NOW}#{newsid}')), (None, None)))
        verify('Snapshot previo conserva explicación histórica tras retirar contacto', lambda: assert_equal(
            domain.read_snapshot(client, table, 'diego', oldsid)['cards'], cards))
        seed({**original(), 'status': 'REMOVED'})
        verify('Original retirado bloquea nuevas republicaciones', lambda: rejected(
            lambda: domain.repost(client, table, 'elena', root, 'removed-post', NOW)))
        verify('Retiro conserva la cadena histórica', lambda: assert_equal(len(events()), 3))
        actions = [domain.put(table, dict(PK='BOUND', SK='META'))] * 2
        verify('Dos acciones al mismo ítem no forman transacción válida', lambda: rejected(lambda: domain.validate_transaction(actions)))
        verify('Más de cien acciones se rechazan antes de llamar AWS', lambda: rejected(lambda: domain.validate_transaction(actions * 51)))
        index_args = dict(TableName=table, IndexName='ActivityByActor', KeyConditionExpression='GSI1PK = :pk',
                          ExpressionAttributeValues=domain.encode({':pk': 'ACTOR#bruno'}))
        activity = client.query(**index_args)
        verify('GSI de actor recupera evento sin duplicar cuerpo', lambda: assert_equal(
            (len(activity['Items']), 'body' in domain.decode(activity['Items'][0])), (1, False)))
        verify('GSI no admite lectura fuertemente consistente', lambda: rejected(lambda: client.query(**index_args, ConsistentRead=True)))
        (BASE / 'transacciones_ejemplo.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2) + '\n')
        report = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'entorno': 'DynamoDB Local / SDK boto3',
                  'boto3_version': boto3.__version__, 'python_version': __import__('platform').python_version(),
                  'dynamodb_local_version_referencia': '3.3.1',
                  'imagen_docker_digest_referencia': 'sha256:ff89bd48ff32cd8d9be5fee8873b65b8854dc408f1afe881be6eb00247bc0dab',
                  'endpoint': args.endpoint, 'tabla_temporal': table,
                  'comprobaciones': len(checks), 'resultado': 'PASS',
                  'limites': ['No valida Cognito, Lambda, permisos IAM ni despliegue AWS.',
                             'No mide precios, propagación temporal de GSI ni rendimiento de producción.',
                             'Sin prueba de carga o carrera simultánea entre procesos; se prueba retiro antes del commit.'],
                  'casos': checks}
        (BASE / 'validacion_dynamodb.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(f'{len(checks)} comprobaciones PASS; transacciones y reporte guardados.')
    finally:
        if created:
            client.delete_table(TableName=table)


if __name__ == '__main__':
    main()
