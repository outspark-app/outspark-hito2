from outspark.publishing.domain.model.value_objects import EventReference
import base64
import binascii
import json
import logging
import hashlib
import time
from uuid import uuid4
from outspark.shared.application.errors import UseCaseError
from outspark.shared.application.models import QueryBudget
from outspark.shared.domain.value_objects import identifier
from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.mapping import record
from outspark.shared.infrastructure.dynamodb.client import cursor_encode, cursor_decode
from outspark.shared.infrastructure.dynamodb.unit_of_work import state_update

class DynamoPublicationsRepository:
    def __init__(self, storage, transactions):
        self.storage, self.transactions = storage, transactions

    def original(self, publication_id):
        return record(self.storage.get(f'POST#{publication_id}', 'META'))

    def event(self, reference):
        ref = EventReference.parse(reference)
        return record(self.storage.get(f'POST#{ref.publication_id}', f'EVENT#{ref.event_id}'))

    def participated(self, publication_id, actor):
        return bool(self.storage.get(f'POST#{publication_id}', f'ACTOR#{actor}'))

    def _request(self, actor, key, payload):
        if not isinstance(key, str) or not 1 <= len(key) <= 128:
            raise UseCaseError(400, 'idempotency_required', 'Se requiere Idempotency-Key de 1 a 128 caracteres.')
        pk, sk = f'USER#{actor}', 'REQUEST#' + hashlib.sha256(key.encode()).hexdigest()
        old = self.storage.get(pk, sk)
        fingerprint = db.digest(payload)
        if old and old['payload_hash'] != fingerprint:
            raise UseCaseError(409, 'idempotency_conflict', 'La clave ya corresponde a otra operación o contenido.')
        return {'PK': pk, 'SK': sk}, fingerprint, old

    def replay(self, actor, key, payload):
        return record(self._request(actor, key, payload)[2] or {}).get('result')

    def _commit(self, actor, key, payload, result, writes, instant, guards):
        request, fingerprint, old = self._request(actor, key, payload)
        if old:
            return {**record(old['result']), 'replayed': True}
        writes = [*writes, db.put(self.storage.table, dict(**request, entity_type='REQUEST', payload_hash=fingerprint,
                                                         result=result, created_at=instant))]
        try:
            self.transactions.commit(writes, guards)
        except UseCaseError as error:
            if error.code != 'write_conflict':
                raise
            saved = self.replay(actor, key, payload)
            if not saved:
                raise
            return {**saved, 'replayed': True}
        return {**result, 'replayed': False}

    def publish(self, draft, key, payload, instant, guards):
        pid, part = str(uuid4()), str(uuid4())
        ref = f'{pid}/{part}'
        original = dict(PK=f'POST#{pid}', SK='META', entity_type='PUBLICATION', publication_id=pid,
                        author_id=draft.author_id, community_id=draft.community_id, body=draft.body,
                        topic_ids=list(draft.topics), visibility='public', status='ACTIVE', root_event_id=ref,
                        created_at=instant, GSI2PK=f'COMM#{draft.community_id}', GSI2SK=f'{instant}#{pid}')
        event = self._event(pid, part, draft.author_id, None, instant)
        writes = [db.put(self.storage.table, original), db.put(self.storage.table, event),
                  self._participation(pid, draft.author_id, ref)]
        return self._commit(draft.author_id, key, payload, {'publication_id': pid, 'event_id': ref}, writes, instant, guards)

    @staticmethod
    def _event(pid, part, actor, parent, instant):
        ref = f'{pid}/{part}'
        return dict(PK=f'POST#{pid}', SK=f'EVENT#{part}', entity_type='EVENT', publication_id=pid,
                    actor_id=actor, parent_event_id=parent, event_id=ref, created_at=instant,
                    GSI1PK=f'ACTOR#{actor}', GSI1SK=f'{instant}#{ref}')

    def _participation(self, pid, actor, ref):
        return db.put(self.storage.table, dict(PK=f'POST#{pid}', SK=f'ACTOR#{actor}', entity_type='PARTICIPATION', event_id=ref))

    def repost(self, actor, parent, key, payload, instant, guards):
        pid, part = parent['publication_id'], str(uuid4())
        ref, parent_ref = f'{pid}/{part}', EventReference.parse(parent['event_id'])
        writes = [db.check(self.storage.table, {'PK': f'POST#{pid}', 'SK': f'EVENT#{parent_ref.event_id}'},
                           'publication_id = :p AND event_id = :e', {':p': pid, ':e': parent['event_id']}),
                  db.put(self.storage.table, self._event(pid, part, actor, parent['event_id'], instant)),
                  self._participation(pid, actor, ref)]
        return self._commit(actor, key, payload, {'publication_id': pid, 'event_id': ref}, writes, instant, guards)

    def comment(self, actor, publication_id, body, key, payload, instant, guards):
        cid = str(uuid4())
        result = dict(comment_id=cid, publication_id=publication_id, author_id=actor, body=body, created_at=instant)
        writes = [db.put(self.storage.table, dict(PK=f'POST#{publication_id}', SK=f'COMMENT#{instant}#{cid}',
                                                 entity_type='COMMENT', status='ACTIVE', **result))]
        return self._commit(actor, key, payload, result, writes, instant, guards)

    def retire(self, publication_id, guards):
        self.transactions.commit([state_update(self.storage.table, f'POST#{publication_id}', 'META', 'REMOVED', 'ACTIVE')], guards)

    @staticmethod
    def _history_cursor(cursor, actor):
        if cursor is None:
            return None
        try:
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 2000:
                raise ValueError()
            payload = json.loads(base64.b64decode(cursor + '=' * (-len(cursor) % 4), altchars=b'-_', validate=True))
            if not isinstance(payload, dict) or set(payload) != {'scope', 'actor', 'key'}:
                raise ValueError()
            if payload['scope'] != 'own_publications' or payload['actor'] != actor:
                raise ValueError()
            key = payload['key']
            if not isinstance(key, dict) or set(key) != {'PK', 'SK', 'GSI1PK', 'GSI1SK'}:
                raise ValueError()
            if any(not isinstance(value, dict) or set(value) != {'S'} or not isinstance(value['S'], str) for value in key.values()):
                raise ValueError()
            if key['GSI1PK']['S'] != f'ACTOR#{actor}' or not key['PK']['S'].startswith('POST#') or not key['SK']['S'].startswith('EVENT#'):
                raise ValueError()
            reference = f"{key['PK']['S'][5:]}/{key['SK']['S'][6:]}"
            EventReference.parse(reference)
            if not key['GSI1SK']['S'].endswith('#' + reference):
                raise ValueError()
            return key
        except (ValueError, KeyError, TypeError, binascii.Error, UnicodeError):
            raise UseCaseError(400, 'invalid_cursor', 'Cursor inválido para tus publicaciones.') from None

    def own_originals(self, actor, limit, cursor):
        # The existing actor index also contains reposts. Page the evaluated events,
        # then hydrate root originals from the strongly consistent base table.
        events, next_key = self.storage.page(
            f'ACTOR#{actor}', limit=limit, cursor=self._history_cursor(cursor, actor), index='ActivityByActor',
        )
        roots = [e for e in events if e.get('parent_event_id') is None and e['actor_id'] == actor]
        posts, missing = self.originals([e['publication_id'] for e in roots], QueryBudget())
        if missing:
            raise UseCaseError(503, 'history_unavailable', 'No pudimos recuperar tus publicaciones completas. Vuelve a intentar.')
        items = [posts[e['publication_id']] for e in roots if e['publication_id'] in posts and posts[e['publication_id']]['author_id'] == actor]
        unavailable = len(roots) - len(items)
        if unavailable:
            logging.getLogger(__name__).error('Own history references %d unavailable originals', unavailable)
        token = cursor_encode({'scope': 'own_publications', 'actor': actor, 'key': next_key}) if next_key else None
        return {'items': items, 'next_cursor': token, 'unavailable_count': unavailable}

    def comments(self, publication_id, limit, cursor):
        pk, prefix = f'POST#{publication_id}', 'COMMENT#'
        items, next_key = self.storage.page(pk, prefix, limit, cursor_decode(cursor, pk, prefix))
        return {'items': [record(i) for i in items if i['status'] == 'ACTIVE'], 'next_cursor': cursor_encode(next_key)}

    def events(self, publication_id, budget=None):
        items, cursor = [], None
        while len(items) <= 1000:
            if budget and budget.pages >= budget.maximum:
                budget.truncated = True
                raise UseCaseError(422, 'provenance_limit', 'Presupuesto insuficiente para recuperar un árbol completo.')
            page, cursor = self.storage.page(f'POST#{publication_id}', 'EVENT#', min(20, 1001 - len(items)), cursor, budget=budget)
            items.extend(page)
            if not cursor:
                break
        if len(items) > 1000 or cursor:
            raise UseCaseError(422, 'provenance_limit', 'La procedencia supera el límite interactivo; no se truncaron rutas.')
        return [record(i) for i in items]

    def originals(self, ids, budget):
        result, unprocessed = {}, 0
        for offset in range(0, len(ids), 100):
            request = {self.storage.table: {'Keys': [db.encode({'PK': f'POST#{p}', 'SK': 'META'}) for p in ids[offset:offset+100]], 'ConsistentRead': True}}
            for attempt in range(3):
                response = self.storage.client.batch_get_item(RequestItems=request, ReturnConsumedCapacity='TOTAL')
                for item in response.get('Responses', {}).get(self.storage.table, []):
                    original = record(db.decode(item)); result[original['publication_id']] = original
                budget.units += sum(float(c.get('CapacityUnits', 0)) for c in response.get('ConsumedCapacity', []))
                request = response.get('UnprocessedKeys', {})
                if not request:
                    break
                if attempt < 2:
                    time.sleep(0.02 * 2 ** attempt)
            if request:
                unprocessed += len(request[self.storage.table]['Keys']); budget.truncated = True
        return result, unprocessed

    def activity(self, actor, limit, budget):
        return [record(i) for i in self.storage.window(f'ACTOR#{actor}', limit=limit, index='ActivityByActor', budget=budget)]

    def community_roots(self, community, limit, budget):
        roots = []
        for row in self.storage.window(f'COMM#{community}', limit=limit, index='PublicationsByCommunity', budget=budget):
            post = self.original(row['publication_id'])
            if post and post['status'] == 'ACTIVE' and post['visibility'] == 'public':
                root = self.event(post['root_event_id'])
                if root:
                    roots.append(root)
        return roots

    def guard(self, guard):
        if guard.kind != 'active_public':
            raise ValueError('Garantía desconocida')
        return db.check(self.storage.table, {'PK': f'POST#{guard.subject}', 'SK': 'META'},
                        '#s = :a AND visibility = :p', {':a': 'ACTIVE', ':p': 'public'}, {'#s': 'status'})
