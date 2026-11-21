from botocore.exceptions import ClientError

from outspark.shared.application.models import now
from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.mapping import record


class DynamoProfilesRepository:
    def __init__(self, storage, transactions):
        self.storage, self.transactions = storage, transactions

    def profile(self, user_id):
        return record(self.storage.get(f"USER#{user_id}", "PROFILE"))

    def ensure_authenticated(self, user_id, name):
        if self.profile(user_id):
            return
        item = dict(
            PK=f"USER#{user_id}",
            SK="PROFILE",
            entity_type="USER",
            uid=user_id,
            name=name,
            status="ACTIVE",
            is_demo=False,
            created_at=now(),
        )
        try:
            self.storage.client.put_item(**db.put(self.storage.table, item)["Put"])
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    def provision_imported(self, users, source):
        from outspark.shared.application.errors import UseCaseError
        from outspark.shared.application.models import now
        from outspark.shared.infrastructure.dynamodb.bulk import batch_get, batches, bulk_write

        preserved, created_at = 0, now()

        def missing_profiles():
            nonlocal preserved
            for chunk in batches(users, 100):
                keys = [{"PK": f"USER#{user['user_id']}", "SK": "PROFILE"} for user in chunk]
                existing = {
                    item["PK"]: item
                    for item in batch_get(self.storage.client, self.storage.table, keys)
                }
                for user, key in zip(chunk, keys, strict=True):
                    old = existing.get(key["PK"])
                    if old:
                        if (
                            old.get("source_dataset_id") != source
                            or int(old.get("dataset_node_id", -1)) != user["node_id"]
                        ):
                            raise UseCaseError(
                                409,
                                "profile_source_conflict",
                                "Una cuenta existente ocupa el identificador de simulación.",
                            )
                        preserved += 1
                        continue
                    yield {
                        **key,
                        "uid": user["user_id"],
                        "name": f"Usuario {user['node_id']}",
                        "entity_type": "USER",
                        "status": "ACTIVE",
                        "is_demo": True,
                        "profile_origin": "dataset_simulation",
                        "source_dataset_id": source,
                        "dataset_node_id": user["node_id"],
                        "created_at": created_at,
                    }

        created = bulk_write(self.storage.client, self.storage.table, missing_profiles())
        return {"created": created, "preserved": preserved, "total": len(users)}

    def preferences(self, user_id):
        return record(self.storage.get(f"USER#{user_id}", "PREFS")) or {
            "topic_ids": [],
            "version": 0,
        }

    def save_preferences(self, preferences, guards):
        item = dict(
            PK=f"USER#{preferences.user_id}",
            SK="PREFS",
            entity_type="PREFERENCES",
            topic_ids=list(preferences.topics),
            version=preferences.version,
        )
        old = preferences.version - 1
        operation = {
            "TableName": self.storage.table,
            "Item": db.encode(item),
            "ConditionExpression": "attribute_not_exists(PK)" if old == 0 else "#v = :v",
        }
        if old:
            operation.update(
                ExpressionAttributeNames={"#v": "version"},
                ExpressionAttributeValues=db.encode({":v": old}),
            )
        self.transactions.commit([{"Put": operation}], guards)
        return record(item)

    def guard(self, guard):
        if guard.kind != "active":
            raise ValueError("Garantía desconocida")
        return db.check(
            self.storage.table,
            {"PK": f"USER#{guard.subject}", "SK": "PROFILE"},
            "attribute_exists(PK) AND #s = :a",
            {":a": "ACTIVE"},
            {"#s": "status"},
        )
