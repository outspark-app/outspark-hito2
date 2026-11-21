import hashlib
import logging
import time
from uuid import uuid4

from botocore.exceptions import ClientError

from outspark.shared.application.errors import UseCaseError
from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.bulk import InventoryDigest, bulk_write

LOG = logging.getLogger("outspark.dataset.import")


class DynamoDatasetImporter:
    def __init__(self, storage, *, workers=4, progress=None):
        self.storage, self.workers, self.progress = storage, workers, progress

    def begin(self, metadata, resume=False):
        self.dataset_id = metadata["dataset_id"]
        self.key = {"PK": f"DATASET#{self.dataset_id}", "SK": "MANIFEST"}
        self.token = uuid4().hex
        old = self.storage.get(self.key["PK"], self.key["SK"])
        if old:
            if (
                old["files"] != metadata["files"]
                or old.get("schema_version") != metadata["schema_version"]
            ):
                raise UseCaseError(
                    409,
                    "dataset_source_conflict",
                    "El dataset registrado tiene otros archivos fuente.",
                )
            if old["status"] == "READY":
                return old
            if not resume:
                raise UseCaseError(
                    409,
                    "import_in_progress",
                    "Importación incompleta; usa --resume después de detener el importador anterior.",
                )
        item = {
            **self.key,
            **metadata,
            "entity_type": "DATASET_MANIFEST",
            "status": "IMPORTING",
            "import_token": self.token,
            "started_at": old["started_at"] if old else int(time.time()),
        }
        args = {
            "TableName": self.storage.table,
            "Item": db.encode(item),
            "ConditionExpression": "attribute_not_exists(PK)" if not old else "#token = :old",
        }
        if old:
            args.update(
                ExpressionAttributeNames={"#token": "import_token"},
                ExpressionAttributeValues=db.encode({":old": old["import_token"]}),
            )
        try:
            self.storage.client.put_item(**args)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise UseCaseError(
                    409, "import_in_progress", "Otro importador obtuvo la exclusión."
                ) from exc
            raise
        return item

    def preview(self, source):
        LOG.info("phase=planning_inventory")
        digest = InventoryDigest()
        for item in source.records():
            digest.add(db.encode(item))
        LOG.info("phase=planned items=%s", digest.count)
        return digest.result()

    def write(self, source):
        digest = InventoryDigest()

        def items():
            for item in source.records():
                encoded = db.encode(item)
                digest.add(encoded)
                yield item

        bulk_write(
            self.storage.client,
            self.storage.table,
            items(),
            workers=self.workers,
            progress=self.progress,
        )
        return digest.result()

    def verify(self, dataset_id, expected, files):
        actual = InventoryDigest()
        root = f"DATASET#{dataset_id}"
        args = {
            "TableName": self.storage.table,
            "ConsistentRead": True,
            "Limit": 100,
            "FilterExpression": "(PK = :root AND begins_with(SK, :node)) OR begins_with(PK, :users) OR begins_with(PK, :sources)",
            "ExpressionAttributeValues": db.encode(
                {
                    ":root": root,
                    ":node": "NODE#",
                    ":users": root + "#USER#",
                    ":sources": root + "#SOURCE#",
                }
            ),
        }
        counters = {
            "nodes": 0,
            "neighbors": 0,
            "friendship_rows": 0,
            "wall_received": 0,
            "wall_sent": 0,
            "source_blocks": 0,
        }
        LOG.info("phase=verifying expected_items=%s page_limit=100", expected["items"])
        reported = 0
        while True:
            response = self.storage.client.scan(**args)
            for encoded in response["Items"]:
                actual.add(encoded)
                item = db.decode(encoded)
                if item["entity_type"] == "HISTORICAL_NODE":
                    counters["nodes"] += 1
                elif item["entity_type"] == "SOURCE_BLOCK":
                    counters["source_blocks"] += 1
                else:
                    key = {
                        "ADJ": "neighbors",
                        "LINK": "friendship_rows",
                        "WALL_IN": "wall_received",
                        "WALL_OUT": "wall_sent",
                    }[item["kind"]]
                    counters[key] += len(item["rows"])
            if actual.count // 10000 > reported:
                reported = actual.count // 10000
                LOG.info("phase=verifying verified_items=%s", actual.count)
            if "LastEvaluatedKey" not in response:
                break
            args["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        if actual.result() != expected:
            raise ValueError(
                f"La base no coincide con los registros preparados: {actual.result()} != {expected}"
            )
        for kind, info in files.items():
            digest = hashlib.sha256()
            for item in db.query(
                self.storage.client, self.storage.table, f"{root}#SOURCE#{kind}", "BLOCK#"
            ):
                digest.update(bytes(item["data"]))
            if digest.hexdigest() != info["sha256"]:
                raise ValueError(f"No se recuperaron íntegramente los bytes de {kind}")
        LOG.info("phase=verified items=%s source_bytes_sha256=PASS", actual.count)
        return {
            "status": "PASS",
            **actual.result(),
            "counts": counters,
            "source_bytes_sha256": "PASS",
        }

    def finish(self, metadata, inventory, verification, profiles):
        item = {
            **self.key,
            **metadata,
            "entity_type": "DATASET_MANIFEST",
            "status": "READY",
            "completed_at": int(time.time()),
            "inventory": inventory,
            "verification": verification,
            "profiles": profiles,
        }
        self.storage.client.put_item(
            TableName=self.storage.table,
            Item=db.encode(item),
            ConditionExpression="#token = :token AND #s = :importing",
            ExpressionAttributeNames={"#token": "import_token", "#s": "status"},
            ExpressionAttributeValues=db.encode({":token": self.token, ":importing": "IMPORTING"}),
        )
        return item
