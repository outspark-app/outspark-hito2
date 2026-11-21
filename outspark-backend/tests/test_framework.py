import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from outspark.bootstrap import compose, create_app
from outspark.persistence import local_storage
from outspark.profiles.domain.model.aggregates import Preferences
from outspark.publishing.domain.model.aggregates import Publication, PublicationDraft
from outspark.seed import seed
from outspark.shared.domain.value_objects import RuleViolation
from tests.support import lambda_adapter, lambda_call, make_server
from tests.test_backend import lambda_event


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.repo = local_storage(prefix="Outspark-local-test-" + uuid4().hex)
        seed(self.repo)
        self.services = compose(self.repo)
        self.app = create_app(self.services, local_demo=True)
        self.server = make_server(self.app, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.server.wait_ready()
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{self.server.server_port}")
        self.addCleanup(self.stop_http)
        self.addCleanup(
            lambda: [
                self.repo.client.delete_table(TableName=r.table)
                for r in self.repo.repositories.values()
            ]
        )

    def stop_http(self):
        self.client.close()
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    def test_openapi_documents_contexts_and_strict_resources(self):
        schema = self.client.get("/openapi.json").json()
        self.assertEqual(schema["info"]["title"], "Outspark API")
        tags = {
            operation["tags"][0] for path in schema["paths"].values() for operation in path.values()
        }
        self.assertTrue(
            {"Profiles", "Connections", "Communities", "Publishing", "Discovery"} <= tags
        )
        self.assertFalse(schema["components"]["schemas"]["PublishResource"]["additionalProperties"])

    def test_payload_limit_and_malformed_json(self):
        headers = {"X-Demo-User": "ana", "Idempotency-Key": "x"}
        self.assertEqual(
            self.client.post(
                "/api/publications", content=b"x" * 17000, headers=headers
            ).status_code,
            413,
        )
        self.assertEqual(
            self.client.post("/api/publications", content="{wrong", headers=headers).status_code,
            400,
        )
        self.assertEqual(
            self.client.put(
                "/api/me/preferences", json={"topic_ids": [], "version": True}, headers=headers
            ).status_code,
            400,
        )

    def test_mangum_uses_authorizer_subject_and_ignores_demo_header(self):
        adapter = lambda_adapter(create_app(self.services, local_demo=False))
        self.assertEqual(
            lambda_call(adapter, lambda_event("/api/me", demo="ana"))["statusCode"], 401
        )
        result = lambda_call(adapter, lambda_event("/api/me", demo="bruno", subject="ana"))
        self.assertEqual(result["statusCode"], 200)
        import json

        self.assertEqual(json.loads(result["body"])["profile"]["uid"], "ana")

    def test_lambda_entrypoint_builds_cloud_app_with_demo_disabled(self):
        from outspark import lambda_handler as entry

        previous = entry._adapter
        entry._adapter = None
        try:
            with patch.object(entry, "cloud_storage", return_value=self.repo):
                result = lambda_call(entry.lambda_handler, lambda_event("/api/me", demo="ana"))
                self.assertEqual(result["statusCode"], 401)
                self.assertEqual(
                    lambda_call(entry.lambda_handler, lambda_event("/api/me", subject="ana"))[
                        "statusCode"
                    ],
                    200,
                )
        finally:
            entry._adapter = previous

    def test_provider_contracts_guard_against_membership_change_before_commit(self):
        # Simulate the change between a permit read and its transaction, with the real adapters.
        command = self.services.publishing_commands
        real_permit = command.communities.permit

        def changed(actor, community, topics):
            guards = real_permit(actor, community, topics)
            self.services.communities_commands.change(actor, community, False)
            return guards

        command.communities.permit = changed
        result = self.client.post(
            "/api/publications",
            json={"community_id": "diseno", "body": "x", "topic_ids": ["diseno"]},
            headers={"X-Demo-User": "ana", "Idempotency-Key": "race-permit"},
        )
        self.assertEqual(result.status_code, 409)
        self.assertEqual(
            self.services.publishing_queries.repository.replay(
                "ana",
                "race-permit",
                {
                    "operation": "publish",
                    "community_id": "diseno",
                    "body": "x",
                    "topic_ids": ["diseno"],
                },
            ),
            None,
        )


class DomainTests(unittest.TestCase):
    def test_publication_rules_and_immutable_retirement(self):
        draft = PublicationDraft.create("ana", "diseno", " idea ", ["diseno"])
        self.assertEqual(draft.body, "idea")
        publication = Publication("p", "ana", "ACTIVE", "public", "p/root")
        with self.assertRaises(RuleViolation):
            publication.retire("bruno")
        retired = publication.retire("ana")
        self.assertEqual(publication.status, "ACTIVE")
        with self.assertRaises(RuleViolation):
            retired.require_active()
        with self.assertRaises(RuleViolation):
            publication.validate_repost("ana", {"event_id": "p/root", "publication_id": "p"}, False)

    def test_preferences_reject_boolean_version_and_duplicate_topics(self):
        for topics, version in [(["diseno"], True), (["diseno", "diseno"], 1), ([], -1)]:
            with self.assertRaises(RuleViolation):
                Preferences.change("ana", topics, version)
