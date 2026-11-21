"""PostgreSQL integration regressions. Set OUTSPARK_POSTGRES_TEST_DSN to run."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

from botocore.exceptions import ClientError
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from psycopg import sql

from outspark.bootstrap import compose, create_app
from outspark.persistence import postgres_local_storage
from outspark.seed import seed
from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.client import local_client
from scripts.migrate_postgres import migrate


@unittest.skipUnless(os.environ.get("OUTSPARK_POSTGRES_TEST_DSN"), "Requires local PostgreSQL")
class PostgresTests(unittest.TestCase):
    def setUp(self):
        self.schema = "outspark_test_" + uuid4().hex
        self.storage = postgres_local_storage(
            os.environ["OUTSPARK_POSTGRES_TEST_DSN"], schema=self.schema
        )
        self.addCleanup(self.drop_fixture)
        self.storage.ensure_tables()

    def drop_fixture(self):
        try:
            with self.storage.client.connection() as connection:
                connection.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema))
                )
        finally:
            self.storage.close()

    def test_copy_preserves_binary_and_text_and_refuses_overwrites(self):
        original = db.encode({"PK": "test", "SK": "META", "text": "día\x00", "data": b"\x00\xff"})
        receipt = self.storage.client.copy_tables({"profiles": iter([original])})
        self.assertEqual(receipt["profiles"]["items"], 1)
        self.assertEqual(self.storage["profiles"].get("test", "META")["text"], "día\x00")
        self.assertEqual(bytes(self.storage["profiles"].get("test", "META")["data"]), b"\x00\xff")
        with self.assertRaisesRegex(ValueError, "ya contiene datos"):
            self.storage.client.copy_tables(
                {"connections": iter([original]), "profiles": iter([original])}
            )
        self.assertIsNone(self.storage["connections"].get("test", "META"))

    def test_rejected_cross_context_guard_rolls_back_writes(self):
        seed(self.storage)
        proposed = db.put(
            "connections", {"PK": "FRIEND#ana#elena", "SK": "META", "status": "ACTIVE"}
        )
        guard = db.check(
            "profiles",
            {"PK": "USER#missing", "SK": "PROFILE"},
            "attribute_exists(PK)",
        )
        with self.assertRaises(ClientError) as conflict:
            db.commit(self.storage.client, [guard, proposed])
        self.assertEqual(
            conflict.exception.response["Error"]["Code"], "TransactionCanceledException"
        )
        self.assertIsNone(self.storage["connections"].get("FRIEND#ana#elena", "META"))

    def test_dynamo_pagination_is_copied_without_resetting_preferences(self):
        repository = SimpleNamespace(table="Outspark-local-profiles")
        client = local_client()
        source = SimpleNamespace(
            client=client, repositories={"profiles": repository}, require_tables=lambda: None
        )
        profile = db.encode({"PK": "USER#fb-1", "SK": "PROFILE", "name": "Usuario 1"})
        preferences = db.encode({"PK": "USER#fb-1", "SK": "PREFS", "version": 7})
        cursor = {field: profile[field] for field in ("PK", "SK")}
        scan = {"TableName": repository.table, "ConsistentRead": True, "Limit": 1000}
        with Stubber(client) as stub:
            stub.add_response("scan", {"Items": [profile], "LastEvaluatedKey": cursor}, scan)
            stub.add_response(
                "scan", {"Items": [preferences]}, {**scan, "ExclusiveStartKey": cursor}
            )
            receipts = migrate(source, self.storage)
            stub.assert_no_pending_responses()
        self.assertEqual(receipts["profiles"]["items"], 2)
        self.assertEqual(self.storage["profiles"].get("USER#fb-1", "PREFS")["version"], 7)

    def test_http_concurrent_publication_replay_and_actor_index_cursor(self):
        seed(self.storage)
        app = create_app(compose(self.storage), local_demo=True)
        body = {"community_id": "diseno", "body": "Una idea", "topic_ids": ["diseno"]}

        def publish(key):
            with TestClient(app) as client:
                return client.post(
                    "/api/publications",
                    json=body,
                    headers={"X-Demo-User": "ana", "Idempotency-Key": key},
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, replay = list(pool.map(publish, ["repeat", "repeat"]))
        self.assertEqual(sorted([first.status_code, replay.status_code]), [200, 201])
        self.assertEqual(first.json()["publication_id"], replay.json()["publication_id"])
        second = publish("different")
        self.assertEqual(second.status_code, 201)
        with TestClient(app) as client:
            headers = {"X-Demo-User": "ana"}
            page = client.get("/api/me/publications", params={"limit": 1}, headers=headers)
            self.assertEqual(page.status_code, 200, page.text)
            cursor = page.json()["next_cursor"]
            self.assertTrue(cursor)
            last = client.get(
                "/api/me/publications", params={"limit": 1, "cursor": cursor}, headers=headers
            )
            self.assertEqual(last.status_code, 200, last.text)
        self.assertIsNone(last.json()["next_cursor"])
        self.assertEqual(
            {first.json()["publication_id"], second.json()["publication_id"]},
            {page.json()["items"][0]["publication_id"], last.json()["items"][0]["publication_id"]},
        )
