from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.mapping import record
from outspark.shared.infrastructure.dynamodb.client import cursor_encode, cursor_decode
from outspark.shared.infrastructure.dynamodb.unit_of_work import state_update

class DynamoConnectionsRepository:
    def __init__(self, storage, transactions):
        self.storage, self.transactions = storage, transactions

    @staticmethod
    def keys(actor, other):
        lo, hi = sorted((actor, other))
        return [(f'FRIEND#{lo}#{hi}', 'META'), (f'USER#{actor}', f'CONTACT#{other}'), (f'USER#{other}', f'CONTACT#{actor}')]

    def contacts(self, actor, limit, cursor):
        pk, prefix = f'USER#{actor}', 'CONTACT#'
        items, next_key = self.storage.page(pk, prefix, limit, cursor_decode(cursor, pk, prefix))
        return {'items': [dict(record(i), contact_id=i['SK'].split('#', 1)[1]) for i in items if i['status'] == 'ACTIVE'],
                'next_cursor': cursor_encode(next_key)}

    def contact_window(self, actor, budget):
        rows = self.storage.window(f'USER#{actor}', 'CONTACT#', 40, budget=budget)
        return [i['SK'].split('#', 1)[1] for i in rows if i['status'] == 'ACTIVE']

    def friendship_states(self, actor, other):
        items = [self.storage.get(*key) for key in self.keys(actor, other)]
        return [i['status'] if i else 'MISSING' for i in items] if any(items) else []

    def remove(self, friendship, actor, guards):
        self.transactions.commit([state_update(self.storage.table, pk, sk, 'REMOVED', 'ACTIVE')
                                  for pk, sk in self.keys(friendship.first, friendship.second)], guards)

    def guard(self, guard):
        if guard.kind != 'active_contact':
            raise ValueError('Garantía desconocida')
        return db.check(self.storage.table, {'PK': f'USER#{guard.subject}', 'SK': f'CONTACT#{guard.related}'},
                        '#s = :a', {':a': 'ACTIVE'}, {'#s': 'status'})
