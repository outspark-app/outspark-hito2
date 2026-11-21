"""Separación física, atomicidad y migración sin pérdida con DynamoDB Local real."""

import gzip
import tempfile
import unittest
from types import SimpleNamespace
from uuid import uuid4

from outspark.migrations.context_tables import backup_rows, migrate
from outspark.persistence import configure
from outspark.shared.application.errors import UseCaseError
from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.client import Repository, local_client
from outspark.shared.infrastructure.dynamodb.unit_of_work import UnitOfWork


class ContextTableTests(unittest.TestCase):
    def test_packaged_schemas_and_context_contracts_match_configuration(self):
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        package = root / "outspark/shared/infrastructure/dynamodb"
        self.assertEqual(
            (package / "table.json").read_bytes(),
            (root / "dynamodb/tabla_dynamodb.json").read_bytes(),
        )
        self.assertEqual(
            (package / "base-table.json").read_bytes(),
            (root / "dynamodb/base_table.json").read_bytes(),
        )
        registry = json.loads((root / "dynamodb/tablas_dynamodb.json").read_text())
        configured = configure(None, "Outspark-dev")
        self.assertEqual(set(registry), set(configured.repositories))
        for owner, repository in configured.repositories.items():
            expected = json.loads((package / repository.schema).read_text())
            expected["TableName"] = repository.table
            self.assertEqual(registry[owner], expected)

    def setUp(self):
        self.client = local_client()
        self.prefix = "Outspark-local-test-" + uuid4().hex
        self.source = Repository(self.client, self.prefix)
        self.target = configure(self.client, self.prefix)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for table in [self.prefix, *(r.table for r in self.target.repositories.values())]:
            try:
                self.client.delete_table(TableName=table)
            except self.client.exceptions.ResourceNotFoundException:
                pass

    def fixture(self):
        self.source.ensure_table()
        rows = [
            {"PK": "USER#ana", "SK": "PROFILE", "status": "ACTIVE"},
            {"PK": "USER#ana", "SK": "PREFS", "version": 8},
            {"PK": "USER#ana", "SK": "MEMBER#diseno", "status": "ACTIVE"},
            {"PK": "USER#ana", "SK": "CONTACT#bruno", "status": "ACTIVE"},
            {"PK": "POST#p", "SK": "META", "body": "Conservar publicación"},
            {"PK": "USER#ana", "SK": "REQUEST#id", "result": {"id": "p"}},
            {"PK": "FEED#s", "SK": "META", "sources": [{"event_id": "p/e"}]},
            {"PK": "DATASET#d#SOURCE#links", "SK": "BLOCK#00000000", "bytes": b"\x00\xfftest"},
        ]
        db.commit(self.client, [db.put(self.source.table, row) for row in rows[:-1]])
        self.client.put_item(TableName=self.source.table, Item=db.encode(rows[-1]))
        return rows

    def execute(self, **kwargs):
        return migrate(self.source, self.target, self.directory.name, quiesced=True, **kwargs)

    def test_complete_copy_preserves_raw_attributes_and_only_publishing_has_indexes(self):
        rows = self.fixture()
        result = self.execute()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["inventory"]["items"], len(rows))
        self.assertTrue(result["source_unchanged"])
        from outspark.migrations.context_tables import owner_of

        for row in rows:
            self.assertEqual(self.source.get(row["PK"], row["SK"]), row)
            self.assertEqual(self.target[owner_of(row)].get(row["PK"], row["SK"]), row)
        self.assertIsNone(self.target["profiles"].get("USER#ana", "MEMBER#diseno"))
        for owner, repository in self.target.repositories.items():
            table = self.client.describe_table(TableName=repository.table)["Table"]
            self.assertEqual(
                len(table.get("GlobalSecondaryIndexes", [])), 2 if owner == "publishing" else 0
            )

    def test_partial_copy_can_resume_and_existing_different_data_is_never_overwritten(self):
        from unittest.mock import patch

        self.fixture()
        with patch.object(self.client, "batch_write_item", side_effect=RuntimeError("interrupted")):
            with self.assertRaises(RuntimeError):
                self.execute()
        db.commit(
            self.client,
            [
                db.put(
                    self.target["profiles"].table, {"PK": "USER#ana", "SK": "PREFS", "version": 8}
                )
            ],
        )
        self.assertEqual(self.execute(resume=True)["status"], "PASS")
        self.client.put_item(
            TableName=self.target["profiles"].table,
            Item=db.encode({"PK": "USER#ana", "SK": "PREFS", "version": 9}),
        )
        with self.assertRaises(ValueError):
            self.execute(resume=True)
        self.assertEqual(self.target["profiles"].get("USER#ana", "PREFS")["version"], 9)
        self.assertEqual(self.source.get("USER#ana", "PREFS")["version"], 8)

    def test_unknown_owner_and_damaged_backup_fail_before_copy(self):
        from pathlib import Path
        from unittest.mock import patch

        self.fixture()
        with patch.object(self.client, "batch_write_item", side_effect=RuntimeError("interrupted")):
            with self.assertRaises(RuntimeError):
                self.execute()
        archive = Path(self.directory.name) / "source.jsonl.gz"
        self.assertEqual(len(list(backup_rows(archive))), 8)
        with gzip.open(archive, "wt") as output:
            output.write("\n".join([]))
        with self.assertRaises(ValueError):
            self.execute(resume=True)
        self.assertIsNone(self.target["profiles"].get("USER#ana", "PROFILE"))
        from outspark.migrations.context_tables import owner_of

        with self.assertRaises(ValueError):
            owner_of({"PK": "USER#ana", "SK": "UNKNOWN"})

    def test_transaction_checks_with_identical_keys_in_different_tables_are_both_enforced(self):
        self.target.ensure_tables()
        key = {"PK": "SHARED#key", "SK": "META"}
        for owner in ("profiles", "communities"):
            db.commit(self.client, [db.put(self.target[owner].table, {**key, "status": "ACTIVE"})])
        transaction = UnitOfWork(self.target)
        for owner in ("profiles", "communities"):
            transaction.register(
                owner,
                lambda guard: db.check(
                    self.target[guard.owner].table,
                    key,
                    "#s = :active",
                    {":active": "ACTIVE"},
                    {"#s": "status"},
                ),
            )
        guards = [SimpleNamespace(owner=owner) for owner in ("profiles", "communities")]
        self.assertEqual(len(transaction.actions(guards)), 2)
        write = db.put(self.target["publishing"].table, {"PK": "POST#p", "SK": "META"})
        self.client.put_item(
            TableName=self.target["communities"].table, Item=db.encode({**key, "status": "REMOVED"})
        )
        with self.assertRaises(UseCaseError) as failure:
            transaction.commit([write], guards)
        self.assertEqual(failure.exception.status, 409)
        self.assertIsNone(self.target["publishing"].get("POST#p", "META"))

    def test_migration_rejects_cloud_or_unquiesced_source(self):
        with self.assertRaises(ValueError):
            migrate(self.source, self.target, self.directory.name)
        cloud = SimpleNamespace(
            table="Outspark-local",
            client=SimpleNamespace(
                meta=SimpleNamespace(endpoint_url="https://dynamodb.us-east-2.amazonaws.com")
            ),
        )
        with self.assertRaises(ValueError):
            migrate(cloud, self.target, self.directory.name, quiesced=True)
