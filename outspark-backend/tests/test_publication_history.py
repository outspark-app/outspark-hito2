"""Own history must outlive feed limits and preserve identity/retirement rules."""

import base64
import json
import unittest
from unittest.mock import patch

from outspark.publishing.interfaces.rest.resources import PublicationsResponse
from tests import test_framework as framework


class PublicationHistoryTests(unittest.TestCase):
    setUp = framework.FrameworkTests.setUp
    stop_http = framework.FrameworkTests.stop_http

    def publish(self, number, actor="ana", community="diseno"):
        response = self.client.post(
            "/api/publications",
            headers={
                "X-Demo-User": actor,
                "Idempotency-Key": f"history-{actor}-{number}",
            },
            json={"community_id": community, "topic_ids": [community], "body": f"Idea {number}"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def history(self, actor="ana", **query):
        return self.client.get("/api/me/publications", headers={"X-Demo-User": actor}, params=query)

    def test_paginates_all_own_originals_independently_of_feed(self):
        posts = [self.publish(i) for i in range(13)]
        other = self.publish("other", "bruno", "tecnologia")
        repost = self.client.post(
            "/api/reposts",
            headers={
                "X-Demo-User": "ana",
                "Idempotency-Key": "history-repost",
            },
            json={"parent_event_id": other["event_id"]},
        )
        self.assertEqual(repost.status_code, 201, repost.text)
        received, cursor, seen = [], None, set()
        for _ in range(20):
            response = self.history(limit=2, **({"cursor": cursor} if cursor else {}))
            self.assertEqual(response.status_code, 200, response.text)
            page = PublicationsResponse.model_validate(response.json())
            received.extend(p.publication_id for p in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
            self.assertNotIn(cursor, seen)
            seen.add(cursor)
        else:
            self.fail("History did not terminate")
        expected = sorted(
            posts, key=lambda p: (p["publication"]["created_at"], p["event_id"]), reverse=True
        )
        self.assertEqual(received, [p["publication_id"] for p in expected])
        self.assertEqual(len(received), 13)
        self.assertNotIn(other["publication_id"], received)

    def test_empty_page_with_continuation_and_retired_body_hydrated_from_base(self):
        own = self.publish("own")
        other = self.publish("other", "bruno", "tecnologia")
        self.client.post(
            "/api/reposts",
            headers={"X-Demo-User": "ana", "Idempotency-Key": "history-branch"},
            json={"parent_event_id": other["event_id"]},
        ).raise_for_status()
        page = self.history(limit=1).json()
        self.assertEqual(page["items"], [])  # Newest activity is a repost.
        self.assertIsNotNone(page["next_cursor"])
        self.client.delete(
            "/api/publications/" + own["publication_id"], headers={"X-Demo-User": "ana"}
        ).raise_for_status()
        response = self.history(limit=1, cursor=page["next_cursor"])
        item = response.json()["items"][0]
        self.assertEqual(item["publication_id"], own["publication_id"])
        self.assertEqual(item["status"], "REMOVED")
        self.assertNotIn("body", item)
        last = response.json()["next_cursor"]
        if last is not None:  # DynamoDB may need a final empty page after an exact limit.
            ending = self.history(limit=1, cursor=last).json()
            self.assertEqual(ending["items"], [])
            self.assertIsNone(ending["next_cursor"])

    def test_history_cursor_is_bound_to_account_query_and_index_shape(self):
        self.publish(1)
        self.publish(2)
        cursor = self.history(limit=1).json()["next_cursor"]
        self.assertIsNotNone(cursor)
        self.assertEqual(self.history("bruno", cursor=cursor).status_code, 400)
        for value in ["bad", "", base64.urlsafe_b64encode(json.dumps([]).encode()).decode()]:
            self.assertEqual(self.history(cursor=value).status_code, 400)
        envelope = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        envelope["key"]["GSI1PK"] = {"S": "ACTOR#bruno"}
        forged = base64.urlsafe_b64encode(json.dumps(envelope).encode()).decode()
        self.assertEqual(self.history(cursor=forged).status_code, 400)
        self.assertEqual(self.history(limit=0).status_code, 400)
        self.assertEqual(self.history(limit=51).status_code, 400)
        self.assertEqual(self.client.get("/api/me/publications").status_code, 401)
        # An extra query parameter cannot select a different owner.
        self.assertTrue(
            all(
                item["author_id"] == "ana"
                for item in self.history(author_id="bruno").json()["items"]
            )
        )

    def test_incomplete_hydration_returns_retryable_error_without_advancing_cursor(self):
        self.publish(1)
        repository = self.services.publishing_queries.repository
        with patch.object(repository, "originals", return_value=({}, 1)):
            response = self.history()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["error"]["code"], "history_unavailable")
        self.assertNotIn("next_cursor", response.json())
        self.assertEqual(len(self.history().json()["items"]), 1)

    def test_missing_original_is_reported_without_blocking_older_history(self):
        from outspark.shared.infrastructure.dynamodb import operations as db

        own = self.publish("older")
        storage = self.repo["publishing"]
        # Deliberately corrupted fixture, not a permitted domain write.
        orphan = dict(
            PK="POST#orphan",
            SK="EVENT#root",
            entity_type="EVENT",
            publication_id="orphan",
            event_id="orphan/root",
            actor_id="ana",
            parent_event_id=None,
            created_at="2099-01-01T00:00:00.000Z",
            GSI1PK="ACTOR#ana",
            GSI1SK="2099-01-01T00:00:00.000Z#orphan/root",
        )
        storage.client.put_item(TableName=storage.table, Item=db.encode(orphan))
        with self.assertLogs(
            "outspark.publishing.infrastructure.persistence.dynamodb.publications", level="ERROR"
        ):
            response = self.history(limit=1)
        self.assertEqual(response.status_code, 200, response.text)
        page = response.json()
        self.assertEqual(page["items"], [])
        self.assertEqual(page["unavailable_count"], 1)
        older = self.history(limit=1, cursor=page["next_cursor"]).json()
        self.assertEqual(older["items"][0]["publication_id"], own["publication_id"])
