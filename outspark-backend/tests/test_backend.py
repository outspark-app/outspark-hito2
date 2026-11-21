"""Integración HTTP + SDK real + DynamoDB Local. Tablas desechables únicas."""

import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from outspark.bootstrap import compose, create_app
from outspark.discovery.domain.services.selection import relevance, select
from outspark.persistence import configure, local_storage
from outspark.publishing.domain.services.traversal import tree_dfs
from outspark.seed import seed
from outspark.shared.application.models import QueryBudget as Budget
from outspark.shared.infrastructure.dynamodb.client import local_client
from tests.support import lambda_adapter, lambda_call, make_server

INSTANT = "2026-10-12T20:00:00.000Z"


def lambda_event(path, demo=None, subject=None):
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "api.example", **({"x-demo-user": demo} if demo else {})},
        "requestContext": {
            "stage": "$default",
            "http": {
                "method": "GET",
                "path": path,
                "sourceIp": "127.0.0.1",
                "protocol": "HTTP/1.1",
            },
        },
        "isBase64Encoded": False,
    }
    if subject:
        event["requestContext"]["authorizer"] = {"jwt": {"claims": {"sub": subject}}}
    return event


class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = local_client()

    def setUp(self):
        self.table = "Outspark-local-test-" + uuid4().hex
        self.repo = configure(self.client, self.table)
        seed(self.repo)
        self.services = compose(self.repo, lambda: INSTANT)
        self.server = make_server(create_app(self.services, local_demo=True), 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.server.wait_ready()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive(), "El servidor HTTP no terminó")
        self.server.server_close()
        for repository in self.repo.repositories.values():
            self.client.delete_table(TableName=repository.table)

    def call(self, method, path, actor="ana", data=None, key=None, extra=None):
        headers = {"Content-Type": "application/json"}
        if actor:
            headers["X-Demo-User"] = actor
        if key:
            headers["Idempotency-Key"] = key
        headers.update(extra or {})
        request = Request(
            self.url + path,
            method=method,
            headers=headers,
            data=json.dumps(data).encode() if data is not None else None,
        )
        try:
            with urlopen(request, timeout=10) as result:
                return result.status, json.loads(result.read()) if result.status != 204 else None
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def publish(self, actor="ana", body="Idea de demo", community="diseno", key="pub"):
        status, result = self.call(
            "POST",
            "/api/publications",
            actor,
            {"community_id": community, "body": body, "topic_ids": [community]},
            key,
        )
        self.assertIn(status, (200, 201), result)
        return result

    def flow(self):
        publication = self.publish()
        status, bruno = self.call(
            "POST", "/api/reposts", "bruno", {"parent_event_id": publication["event_id"]}, "b"
        )
        self.assertEqual(status, 201)
        status, carla = self.call(
            "POST", "/api/reposts", "carla", {"parent_event_id": bruno["event_id"]}, "c"
        )
        self.assertEqual(status, 201)
        return publication, bruno, carla

    def test_real_http_complete_flow_and_two_routes(self):
        publication, bruno, carla = self.flow()
        status, feed = self.call(
            "POST", "/api/feed/snapshots", "diego", {"strategy": "chronological"}
        )
        self.assertEqual(status, 201, feed)
        self.assertEqual(len(feed["cards"]), 1)
        self.assertEqual(feed["cards"][0]["publication"]["body"], "Idea de demo")
        path = f"/api/feed/{feed['snapshot_id']}/cards/{publication['publication_id']}/provenance"
        status, result = self.call("GET", path, "diego")
        self.assertEqual(status, 200, result)
        routes = {tuple(e["actor_id"] for e in r["events"]) for r in result["routes"]}
        self.assertIn(("ana", "bruno"), routes)
        self.assertIn(("ana", "bruno", "carla"), routes)
        self.assertEqual(result["tree"]["event_count"], 3)
        self.assertEqual([n["depth"] for n in result["tree"]["dfs"]], [0, 1, 2])

    def test_identity_required_and_no_body_impersonation(self):
        self.assertEqual(self.call("GET", "/api/me", None)[0], 401)
        self.assertEqual(self.call("GET", "/api/me", "missing")[0], 403)
        self.assertEqual(
            self.call(
                "POST",
                "/api/publications",
                "ana",
                {
                    "author_id": "bruno",
                    "community_id": "diseno",
                    "body": "Spoof",
                    "topic_ids": ["diseno"],
                },
                "spoof",
            )[0],
            400,
        )
        event = lambda_event("/api/me", demo="ana")
        adapter = lambda_adapter(create_app(self.services, local_demo=False))
        self.assertEqual(lambda_call(adapter, event)["statusCode"], 401)

    def test_invalid_inputs_and_unknown_route(self):
        for body, topics in [
            ("", ["diseno"]),
            ("x" * 1001, ["diseno"]),
            ("x", ["diseno", "diseno"]),
            ("x", ["missing"]),
            ("x", "diseno"),
        ]:
            self.assertEqual(
                self.call(
                    "POST",
                    "/api/publications",
                    "ana",
                    {"body": body, "topic_ids": topics, "community_id": "diseno"},
                    "invalid",
                )[0],
                400,
            )
        self.assertEqual(
            self.call(
                "POST",
                "/api/publications",
                "ana",
                {"body": "x", "topic_ids": ["diseno"], "community_id": "diseno"},
            )[0],
            400,
        )
        self.assertEqual(self.call("GET", "/api/missing")[0], 404)
        self.assertEqual(
            self.call("POST", "/api/feed/snapshots", data={"strategy": "wrong"})[0], 400
        )

    def test_idempotency_and_retry_after_membership_removal(self):
        first = self.publish()
        second = self.publish()
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertTrue(second["replayed"])
        self.assertEqual(
            self.call(
                "POST",
                "/api/publications",
                "ana",
                {"community_id": "diseno", "body": "Changed", "topic_ids": ["diseno"]},
                "pub",
            )[0],
            409,
        )
        self.call("DELETE", "/api/me/communities/diseno", "ana")
        self.assertEqual(self.publish()["event_id"], first["event_id"])
        self.assertEqual(
            len(self.services.publishing_queries.repository.events(first["publication_id"])), 1
        )

    def test_membership_mirrors_and_authorization(self):
        self.assertEqual(
            self.call(
                "POST",
                "/api/publications",
                "bruno",
                {"community_id": "diseno", "body": "No", "topic_ids": ["diseno"]},
                "b",
            )[0],
            403,
        )
        for method, state in [("PUT", "ACTIVE"), ("DELETE", "REMOVED"), ("PUT", "ACTIVE")]:
            self.assertEqual(self.call(method, "/api/me/communities/diseno", "bruno")[0], 200)
            self.assertEqual(
                self.repo["communities"].get("USER#bruno", "MEMBER#diseno")["status"], state
            )
            self.assertEqual(
                self.repo["communities"].get("COMM#diseno", "MEMBER#bruno")["status"], state
            )
        self.publish("bruno", key="after-join")

    def test_repost_duplicate_self_and_bad_parent(self):
        publication, bruno, carla = self.flow()
        self.assertEqual(
            self.call(
                "POST", "/api/reposts", "ana", {"parent_event_id": publication["event_id"]}, "own"
            )[0],
            409,
        )
        self.assertEqual(
            self.call(
                "POST", "/api/reposts", "bruno", {"parent_event_id": carla["event_id"]}, "b2"
            )[0],
            409,
        )
        self.assertEqual(
            self.call("POST", "/api/reposts", "elena", {"parent_event_id": "wrong"}, "bad")[0], 400
        )
        self.assertEqual(
            self.call(
                "POST", "/api/reposts", "elena", {"parent_event_id": "missing/event"}, "missing"
            )[0],
            404,
        )

    def test_concurrent_reposts_unique_and_recoverable(self):
        publication = self.publish()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(
                pool.map(
                    lambda i: self.call(
                        "POST",
                        "/api/reposts",
                        "bruno",
                        {"parent_event_id": publication["event_id"]},
                        f"race-{i}",
                    ),
                    range(4),
                )
            )
        self.assertEqual(sum(status == 201 for status, _ in results), 1, results)
        self.assertTrue(all(status in (201, 409) for status, _ in results), results)
        self.assertEqual(
            len(self.services.publishing_queries.repository.events(publication["publication_id"])),
            2,
        )
        winning = next(i for i, result in enumerate(results) if result[0] == 201)
        status, replay = self.call(
            "POST",
            "/api/reposts",
            "bruno",
            {"parent_event_id": publication["event_id"]},
            f"race-{winning}",
        )
        self.assertEqual(status, 200)
        self.assertEqual(replay["event_id"], results[winning][1]["event_id"])

    def test_concurrent_same_key_does_not_duplicate(self):
        publication = self.publish()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(
                pool.map(
                    lambda _: self.call(
                        "POST",
                        "/api/reposts",
                        "bruno",
                        {"parent_event_id": publication["event_id"]},
                        "same-key",
                    ),
                    range(3),
                )
            )
        self.assertTrue(all(s in (200, 201, 409) for s, _ in results), results)
        self.assertEqual(sum(s == 201 for s, _ in results), 1)
        self.assertEqual(
            len(self.services.publishing_queries.repository.events(publication["publication_id"])),
            2,
        )
        replay = self.call(
            "POST",
            "/api/reposts",
            "bruno",
            {"parent_event_id": publication["event_id"]},
            "same-key",
        )
        self.assertEqual(replay[0], 200)
        self.assertEqual(
            len({r["event_id"] for s, r in results if s in (200, 201)} | {replay[1]["event_id"]}), 1
        )

    def test_snapshot_owner_and_reasons_survive_contact_removal(self):
        publication, _, _ = self.flow()
        status, feed = self.call(
            "POST", "/api/feed/snapshots", "diego", {"strategy": "chronological"}
        )
        self.assertEqual(status, 201)
        sid, pid = feed["snapshot_id"], publication["publication_id"]
        path = f"/api/feed/{sid}/cards/{pid}/provenance"
        self.assertEqual(self.call("GET", path, "ana")[0], 403)
        self.assertEqual(self.call("GET", f"/api/feed/{sid}", "ana")[0], 403)
        before = self.call("GET", path, "diego")[1]["routes"]
        self.assertEqual(self.call("DELETE", "/api/me/contacts/bruno", "diego")[0], 200)
        self.assertEqual(
            self.repo["connections"].get("USER#bruno", "CONTACT#diego")["status"], "REMOVED"
        )
        self.assertEqual(self.call("GET", path, "diego")[1]["routes"], before)
        newer = self.call("POST", "/api/feed/snapshots", "diego", {"strategy": "chronological"})[1]
        reasons = [r for c in newer["cards"] for s in c["sources"] for r in s["reasons"]]
        self.assertFalse(any(r.get("contact_id") == "bruno" for r in reasons))
        self.assertEqual(self.call("GET", "/api/feed/missing", "diego")[0], 404)

    def test_comment_pagination_and_idempotency(self):
        publication = self.publish()
        path = f"/api/publications/{publication['publication_id']}/comments"
        for i in range(3):
            self.assertEqual(
                self.call("POST", path, "bruno", {"body": str(i)}, f"comment-{i}")[0], 201
            )
        self.assertEqual(self.call("POST", path, "bruno", {"body": "0"}, "comment-0")[0], 200)
        first = self.call("GET", path + "?limit=2")[1]
        self.assertEqual(len(first["items"]), 2)
        self.assertTrue(first["next_cursor"])
        second = self.call("GET", path + "?limit=2&cursor=" + first["next_cursor"])[1]
        self.assertEqual(len(second["items"]), 1)
        self.assertEqual(self.call("GET", path + "?cursor=wrong")[0], 400)
        self.assertEqual(self.call("GET", path + "?limit=0")[0], 400)

    def test_retired_content_hidden_and_new_writes_rejected(self):
        publication, _, _ = self.flow()
        feed = self.call("POST", "/api/feed/snapshots", "diego", {"strategy": "chronological"})[1]
        path = f"/api/publications/{publication['publication_id']}"
        self.assertEqual(
            self.call("POST", path + "/comments", "diego", {"body": "Antes"}, "before-retirement")[
                0
            ],
            201,
        )
        self.assertEqual(self.call("DELETE", path, "bruno")[0], 403)
        self.assertEqual(self.call("DELETE", path, "ana")[0], 200)
        self.assertNotIn("body", self.call("GET", path, "diego")[1])
        self.assertEqual(
            self.call("POST", path + "/comments", "diego", {"body": "Antes"}, "before-retirement")[
                0
            ],
            410,
        )
        self.assertEqual(
            self.call("POST", path + "/comments", "diego", {"body": "No"}, "retired")[0], 410
        )
        self.assertEqual(
            self.call(
                "POST",
                "/api/reposts",
                "diego",
                {"parent_event_id": publication["event_id"]},
                "retired",
            )[0],
            410,
        )
        provenance = self.call(
            "GET",
            f"/api/feed/{feed['snapshot_id']}/cards/{publication['publication_id']}/provenance",
            "diego",
        )
        self.assertEqual(provenance[0], 200)
        self.assertNotIn("body", provenance[1]["publication"])
        self.assertEqual(
            self.call("POST", "/api/feed/snapshots", "diego", {"strategy": "chronological"})[1][
                "cards"
            ],
            [],
        )

    def test_preferences_optimistic_version(self):
        self.assertEqual(
            self.call(
                "PUT", "/api/me/preferences", "diego", {"topic_ids": ["tecnologia"], "version": 1}
            )[0],
            200,
        )
        self.assertEqual(
            self.call(
                "PUT", "/api/me/preferences", "diego", {"topic_ids": ["diseno"], "version": 1}
            )[0],
            409,
        )
        self.assertEqual(self.call("GET", "/api/me", "diego")[1]["preferences"]["version"], 2)

    def test_comparison_uses_identical_materialized_inputs(self):
        self.flow()
        self.publish("bruno", "Idea tecnológica", "tecnologia", "technology")
        result = self.call("POST", "/api/feed/comparisons", "diego")
        self.assertEqual(result[0], 201, result)
        chronological, diverse = (result[1]["feeds"][s] for s in ("chronological", "diverse"))
        self.assertEqual(
            chronological["selection"]["candidate_hash"], diverse["selection"]["candidate_hash"]
        )
        self.assertEqual(
            chronological["selection"]["reference_at"], diverse["selection"]["reference_at"]
        )
        self.assertEqual(
            chronological["selection"]["preferences"], diverse["selection"]["preferences"]
        )
        self.assertLessEqual(chronological["selection"]["retrieval"]["query_pages"], 60)

    def test_new_service_and_reseed_preserve_data(self):
        publication = self.publish()
        self.call("DELETE", "/api/me/communities/diseno", "ana")
        seed(local_storage(prefix=self.table))
        restarted = compose(local_storage(prefix=self.table))
        self.assertEqual(
            restarted.publishing_queries.original(publication["publication_id"])["body"],
            "Idea de demo",
        )
        self.assertEqual(
            self.repo["communities"].get("USER#ana", "MEMBER#diseno")["status"], "REMOVED"
        )

    def test_local_cors_and_health(self):
        self.assertEqual(self.call("GET", "/api/health", None)[0], 200)
        self.assertEqual(
            self.call("GET", "/api/me", "ana", extra={"Origin": "https://evil.example"})[0], 403
        )
        self.assertEqual(
            self.call("OPTIONS", "/api/me", extra={"Origin": "http://127.0.0.1:5178"})[0], 204
        )

    def test_query_budget_stops_reads(self):
        budget = Budget(maximum=1)
        self.repo["communities"].window("CATALOG#COMM", "COMM#", 2, budget=budget)
        self.assertEqual(budget.pages, 1)
        self.assertTrue(budget.truncated)
        items = self.repo["communities"].window("CATALOG#COMM", "COMM#", 20, budget=budget)
        self.assertEqual(items, [])


class AlgorithmTests(unittest.TestCase):
    def test_dfs_branches_missing_parent_cycle_and_long_chain(self):
        def event(ref, parent):
            return {"event_id": ref, "parent_event_id": parent, "publication_id": "p"}

        self.assertEqual(
            [
                v["event_id"]
                for v in tree_dfs(
                    [event("a", None), event("b", "a"), event("c", "b"), event("d", "a")], "a"
                )
            ],
            ["a", "b", "c", "d"],
        )
        for events in (
            [event("a", None), event("b", "missing")],
            [event("a", None), event("b", "c"), event("c", "b")],
        ):
            with self.assertRaises(ValueError):
                tree_dfs(events, "a")
        chain = [event(str(i), str(i - 1) if i else None) for i in range(1500)]
        self.assertEqual(len(tree_dfs(chain, "0")), 1500)

    def test_greedy_feasibility_and_exact_small_reference(self):
        originals = {
            str(i): {
                "author_id": "a" if i < 3 else "b",
                "community_id": "x" if i < 3 else "y",
                "topic_ids": ["diseno"],
                "created_at": INSTANT,
            }
            for i in range(4)
        }
        candidates = {pid: {"sources": [], "latest_at": INSTANT} for pid in originals}
        selected = select(candidates, originals, ["diseno"], INSTANT, "diverse", k=3)
        self.assertEqual(len(selected), 3)
        self.assertLessEqual(
            sum(originals[c["publication_id"]]["author_id"] == "a" for c in selected), 2
        )

        def objective(ids):
            return sum(relevance(originals[p], ["diseno"], INSTANT) for p in ids) + 0.3 * len(
                {originals[p]["community_id"] for p in ids}
            )

        feasible = [
            subset
            for n in range(4)
            for subset in combinations(originals, n)
            if all(sum(originals[p]["author_id"] == a for p in subset) <= 2 for a in ("a", "b"))
        ]
        self.assertAlmostEqual(
            objective([c["publication_id"] for c in selected]), max(map(objective, feasible))
        )


if __name__ == "__main__":
    unittest.main()
