import json
from uuid import uuid4
from outspark.shared.application.errors import UseCaseError
from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.mapping import record

class DynamoSnapshotsRepository:
    def __init__(self, storage, transactions):
        self.storage, self.transactions = storage, transactions

    def snapshot(self, snapshot_id):
        return record(self.storage.get(f'FEED#{snapshot_id}', 'META'))

    def save(self, viewer, cards, instant, strategy, metadata, guards):
        sid = str(uuid4())
        item = dict(PK=f'FEED#{sid}', SK='META', entity_type='FEED_SNAPSHOT', snapshot_id=sid, viewer_id=viewer,
                    strategy=strategy, algorithm_version='feed-v1', generated_at=instant, cards=cards,
                    source_count=sum(len(c['sources']) for c in cards),
                    limits={'candidates': 200, 'cards': 10, 'contacts': 20, 'communities': 10}, selection=metadata)
        if len(json.dumps(item, ensure_ascii=False, separators=(',', ':')).encode()) > 128 * 1024:
            raise UseCaseError(422, 'snapshot_limit', 'Snapshot excede límite interno de 128 KiB.')
        pointer = dict(PK=f'USER#{viewer}', SK=f'FEED#{instant}#{sid}', entity_type='FEED_POINTER',
                       snapshot_id=sid, generated_at=instant)
        self.transactions.commit([db.put(self.storage.table, item), db.put(self.storage.table, pointer)], guards)
        return sid
