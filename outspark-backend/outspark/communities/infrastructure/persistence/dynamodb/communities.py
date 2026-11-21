from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.mapping import record
from outspark.shared.infrastructure.dynamodb.client import cursor_encode, cursor_decode
from outspark.shared.infrastructure.dynamodb.unit_of_work import state_update

class DynamoCommunitiesRepository:
    def __init__(self, storage, transactions):
        self.storage, self.transactions = storage, transactions

    def community(self, community):
        return record(self.storage.get(f'COMM#{community}', 'META'))

    def topic_exists(self, topic):
        return bool(self.storage.get('CATALOG#TOPIC', f'TOPIC#{topic}'))

    def member(self, actor, community):
        row = self.storage.get(f'USER#{actor}', f'MEMBER#{community}')
        return bool(row and row['status'] == 'ACTIVE')

    def _page(self, pk, prefix, limit, cursor):
        items, next_key = self.storage.page(pk, prefix, limit, cursor_decode(cursor, pk, prefix))
        return {'items': [dict(record(i), **({'community_id': i['SK'].split('#', 1)[1]} if prefix == 'MEMBER#' else {}))
                          for i in items if i.get('status', 'ACTIVE') == 'ACTIVE'], 'next_cursor': cursor_encode(next_key)}

    def catalog(self, kind, limit, cursor):
        return self._page('CATALOG#COMM' if kind == 'communities' else 'CATALOG#TOPIC',
                          'COMM#' if kind == 'communities' else 'TOPIC#', limit, cursor)

    def memberships(self, actor, limit, cursor):
        return self._page(f'USER#{actor}', 'MEMBER#', limit, cursor)

    def member_window(self, actor, budget):
        return [i['SK'].split('#', 1)[1] for i in self.storage.window(f'USER#{actor}', 'MEMBER#', 20, budget=budget)
                if i['status'] == 'ACTIVE']

    def catalog_window(self, budget):
        return [i['community_id'] for i in self.storage.window('CATALOG#COMM', 'COMM#', 20, budget=budget)
                if i['status'] == 'ACTIVE']

    @staticmethod
    def keys(actor, community):
        return [(f'USER#{actor}', f'MEMBER#{community}'), (f'COMM#{community}', f'MEMBER#{actor}')]

    def membership_states(self, actor, community):
        items = [self.storage.get(*key) for key in self.keys(actor, community)]
        return [i['status'] if i else 'MISSING' for i in items] if any(items) else []

    def save_membership(self, membership, states, instant, guards):
        writes = []
        for position, (pk, sk) in enumerate(self.keys(membership.user_id, membership.community_id)):
            if states:
                writes.append(state_update(self.storage.table, pk, sk, membership.status, states[position]))
            else:
                writes.append(db.put(self.storage.table, dict(PK=pk, SK=sk, entity_type='MEMBERSHIP',
                                                             status=membership.status, created_at=instant)))
        self.transactions.commit(writes, guards)

    def guard(self, guard):
        if guard.kind == 'active':
            key = {'PK': f'COMM#{guard.subject}', 'SK': 'META'}
        elif guard.kind == 'membership':
            key = {'PK': f'USER#{guard.subject}', 'SK': f'MEMBER#{guard.related}'}
        elif guard.kind == 'topic':
            return db.check(self.storage.table, {'PK': 'CATALOG#TOPIC', 'SK': f'TOPIC#{guard.subject}'}, 'attribute_exists(PK)')
        else:
            raise ValueError('Garantía desconocida')
        return db.check(self.storage.table, key, '#s = :a', {':a': 'ACTIVE'}, {'#s': 'status'})
