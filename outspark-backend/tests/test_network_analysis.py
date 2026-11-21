"""Importación íntegra en tablas temporales y consumo del histórico por la app."""

import gzip
import tempfile
import unittest
from pathlib import Path

from outspark.bootstrap import compose_import
from outspark.network_analysis.application.queryservices.datasets import DatasetQueries
from outspark.network_analysis.domain.model.dataset import DEFAULT_DATASET
from outspark.network_analysis.domain.services.reach import breadth_first_reach
from outspark.network_analysis.infrastructure.importing.importer import DynamoDatasetImporter
from outspark.network_analysis.infrastructure.importing.source import PreparedDataset
from outspark.network_analysis.infrastructure.persistence.dynamodb.datasets import (
    DynamoDatasetsRepository,
)
from outspark.network_analysis.interfaces.rest.resources import (
    DatasetResponse,
    FriendshipRecordsResponse,
    NeighborsResponse,
    NodeResponse,
    NodesResponse,
    ReachResponse,
    WallEventsResponse,
)
from outspark.shared.infrastructure.dynamodb import operations as db
from tests import test_framework as framework

BASE = f"/api/network/datasets/{DEFAULT_DATASET}"


class NetworkTests(unittest.TestCase):
    setUp = framework.FrameworkTests.setUp
    stop_http = framework.FrameworkTests.stop_http

    def prepare_source(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        links, wall = [Path(temporary.name) / name for name in ("links.txt.gz", "wall.txt.gz")]
        with gzip.open(links, "wt") as output:
            output.write("1\t2\t\\N\n2\t1\t100\n1\t2\t100\n2\t3\t200\n")
        with gzip.open(wall, "wt") as output:
            output.write("4\t1\t300\n1\t4\t301\n4\t4\t302\n")
            for i in range(513):
                output.write(f"4\t1\t{500 + i}\n")
        source = PreparedDataset(DEFAULT_DATASET, links, wall, verify_reference=False)
        self.addCleanup(source.close)
        return source

    def import_source(self):
        source = self.prepare_source()
        result = compose_import(self.repo).execute(source)
        self.assertEqual(result["status"], "READY")
        return source, result

    def test_publication_diffusion_checks_author_and_direct_contacts(self):
        self.import_source()
        owner = {"X-Demo-User": "ana", "Idempotency-Key": "diffusion-test"}
        created = self.client.post(
            "/api/publications",
            headers=owner,
            json={"community_id": "diseno", "body": "Prueba BFS", "topic_ids": ["diseno"]},
        )
        self.assertEqual(created.status_code, 201, created.text)
        route = "/api/publications/" + created.json()["publication_id"] + "/diffusion"
        settings = {"origin": 2, "max_hops": 3, "slots": 1, "custom_contacts": [3]}
        response = self.client.post(route, headers=owner, json=settings)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["custom"]["reachable"], 1)
        self.assertEqual(response.json()["custom"]["contacts"], [3])
        self.assertEqual(
            self.client.post(route, headers={"X-Demo-User": "bruno"}, json=settings).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                route, headers=owner, json={**settings, "custom_contacts": [4]}
            ).status_code,
            400,
        )

    def get(self, suffix, model, actor="ana"):
        response = self.client.get(BASE + suffix, headers={"X-Demo-User": actor})
        self.assertEqual(response.status_code, 200, response.text)
        model.model_validate(response.json())
        return response.json()

    def test_import_keeps_all_source_rows_null_dates_wall_only_users_and_original_bytes(self):
        source, result = self.import_source()
        self.assertEqual(result["counts"]["nodes"], 4)
        self.assertEqual(result["counts"]["friendship_nodes"], 3)
        self.assertEqual(result["counts"]["wall_only_nodes"], 1)
        self.assertEqual(result["counts"]["friendship_rows"], 4)
        self.assertEqual(result["counts"]["unique_friendships"], 2)
        self.assertEqual(result["counts"]["wall_events"], 516)
        self.assertEqual(result["verification"]["counts"]["wall_sent"], 516)
        self.assertEqual(result["verification"]["counts"]["wall_received"], 516)
        self.assertEqual(result["verification"]["source_bytes_sha256"], "PASS")
        rows = self.get("/nodes/1/friendship-records", FriendshipRecordsResponse)["items"]
        self.assertEqual([row["source_line"] for row in rows], [1, 3])
        self.assertIsNone(rows[0]["timestamp"])
        self.assertEqual(rows[1]["timestamp"], 100)
        wall = self.get("/nodes/4", NodeResponse)
        self.assertFalse(wall["in_friendship_graph"])
        self.assertEqual(wall["degree"], 0)
        self.assertTrue(source.metadata["files"])

    def test_import_replays_without_resetting_profile_preferences_or_demo_data(self):
        source, first = self.import_source()
        changed = self.client.put(
            "/api/me/preferences",
            headers={"X-Demo-User": "fb-1"},
            json={"topic_ids": ["diseno"], "version": 0},
        )
        self.assertEqual(changed.status_code, 200)
        second = compose_import(self.repo).execute(source)
        self.assertTrue(second["replayed"])
        self.assertEqual(first["inventory"], second["inventory"])
        me = self.client.get("/api/me", headers={"X-Demo-User": "fb-1"}).json()
        self.assertEqual(me["preferences"]["version"], 1)
        self.assertEqual(me["preferences"]["topic_ids"], ["diseno"])
        self.assertEqual(self.repo["profiles"].get("USER#ana", "PROFILE")["name"], "Ana")

    def test_verification_rejects_missing_chunks_even_after_ready(self):
        source, first = self.import_source()
        self.repo.client.delete_item(
            TableName=self.repo["network_analysis"].table,
            Key=db.encode({"PK": f"DATASET#{DEFAULT_DATASET}#USER#1", "SK": "ADJ#00000000"}),
        )
        with self.assertRaises(ValueError):
            compose_import(self.repo).execute(source)
        self.assertEqual(first["verification"]["status"], "PASS")

    def test_resume_after_writing_all_data_verifies_it_without_rewriting(self):
        from unittest.mock import patch

        source = self.prepare_source()
        writer = DynamoDatasetImporter(self.repo["network_analysis"])
        writer.begin(source.metadata)
        writer.write(source)
        resumed = compose_import(self.repo)
        with patch.object(
            resumed.repository,
            "write",
            side_effect=AssertionError("No debe reescribir datos completos"),
        ):
            result = resumed.execute(source, resume=True)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["verification"]["counts"]["friendship_rows"], 4)

    def test_all_seven_network_operations_have_live_response_models_and_correct_bfs(self):
        source, _ = self.import_source()
        source.files["links"].unlink()
        source.files["wall"].unlink()
        self.get("", DatasetResponse)
        nodes = self.get("/nodes?limit=2", NodesResponse)
        self.assertEqual(len(nodes["items"]), 2)
        self.assertIsNotNone(nodes["next_cursor"])
        self.get("/nodes/1", NodeResponse)
        neighbors = self.get("/nodes/1/neighbors", NeighborsResponse)
        self.assertEqual([row["node_id"] for row in neighbors["items"]], [2])
        self.get("/nodes/1/friendship-records", FriendshipRecordsResponse)
        self.get("/nodes/4/wall-events", WallEventsResponse)
        result = self.get("/nodes/1/reach", ReachResponse)
        self.assertEqual([row["new_nodes"] for row in result["rounds"]], [1, 1, 0])
        self.assertTrue(result["complete"])

    def test_wall_pagination_crosses_chunks_preserves_direction_and_rejects_foreign_cursor(self):
        self.import_source()
        service = DatasetQueries(DynamoDatasetsRepository(self.repo["network_analysis"]))
        cursor, events = None, []
        while True:
            page = service.records(DEFAULT_DATASET, 4, "wall_received", 50, cursor)
            events.extend(page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        self.assertEqual(len(events), 515)
        self.assertEqual(len({e["source_line"] for e in events}), 515)
        self.assertTrue(all(e["wall_owner_id"] == 4 and not e["content_available"] for e in events))
        self.assertEqual(events[0]["timestamp"], 1012)
        incoming = service.records(DEFAULT_DATASET, 4, "wall_received", 1, None)
        with self.assertRaises(Exception) as error:
            service.records(DEFAULT_DATASET, 1, "wall_received", 1, incoming["next_cursor"])
        self.assertEqual(error.exception.code, "invalid_cursor")
        outgoing = self.get("/nodes/1/wall-events?direction=sent", WallEventsResponse)
        self.assertEqual(outgoing["items"][0]["author_id"], 1)

    def test_real_graph_contacts_drive_publishing_reposting_and_feed_with_atomic_guards(self):
        self.import_source()
        headers = {"X-Demo-User": "fb-1", "Origin": str(self.client.base_url).rstrip("/")}
        joined = self.client.put("/api/me/communities/diseno", headers=headers)
        self.assertEqual(joined.status_code, 200)
        published = self.client.post(
            "/api/publications",
            headers={**headers, "Idempotency-Key": "historical-simulation"},
            json={
                "community_id": "diseno",
                "body": "Simulación sobre la topología histórica.",
                "topic_ids": ["diseno"],
            },
        )
        self.assertEqual(published.status_code, 201, published.text)
        reposted = self.client.post(
            "/api/reposts",
            headers={"X-Demo-User": "fb-2", "Idempotency-Key": "historical-repost"},
            json={"parent_event_id": published.json()["event_id"]},
        )
        self.assertEqual(reposted.status_code, 201, reposted.text)
        contacts = self.client.get("/api/me/contacts", headers={"X-Demo-User": "fb-3"}).json()
        self.assertEqual(contacts["items"][0]["contact_id"], "fb-2")
        feed = self.client.post(
            "/api/feed/snapshots",
            headers={"X-Demo-User": "fb-3"},
            json={"strategy": "chronological"},
        )
        self.assertEqual(feed.status_code, 201, feed.text)
        self.assertEqual(
            feed.json()["cards"][0]["publication_id"], published.json()["publication_id"]
        )
        sid, pid = feed.json()["snapshot_id"], published.json()["publication_id"]
        proof = self.client.get(
            f"/api/feed/{sid}/cards/{pid}/provenance", headers={"X-Demo-User": "fb-3"}
        )
        self.assertEqual(proof.status_code, 200)
        routes = [[e["actor_id"] for e in route["events"]] for route in proof.json()["routes"]]
        self.assertIn(["fb-1", "fb-2"], routes)
        self.assertEqual(
            self.client.delete(
                "/api/me/contacts/fb-2", headers={"X-Demo-User": "fb-3"}
            ).status_code,
            409,
        )

    def test_importing_dataset_is_hidden_and_bfs_read_budget_never_reports_partial_success(self):
        from types import SimpleNamespace

        cloud = SimpleNamespace(
            table="Outspark-local",
            client=SimpleNamespace(
                meta=SimpleNamespace(endpoint_url="https://dynamodb.us-east-2.amazonaws.com")
            ),
        )
        with self.assertRaises(ValueError):
            compose_import(cloud)
        source = self.prepare_source()
        importer = DynamoDatasetImporter(self.repo["network_analysis"])
        importer.begin(source.metadata)
        response = self.client.get(BASE, headers={"X-Demo-User": "ana"})
        self.assertEqual(response.status_code, 409)
        compose_import(self.repo).execute(source, resume=True)
        repository = DynamoDatasetsRepository(self.repo["network_analysis"])
        with self.assertRaises(Exception) as error:
            repository.neighbors_many(DEFAULT_DATASET, [1], {"calls": 0, "maximum": 0})
        self.assertEqual(error.exception.status, 422)


class BreadthFirstTests(unittest.TestCase):
    def test_cycles_disconnected_components_and_levels(self):
        graph = {1: [2, 3], 2: [1, 3], 3: [1, 2, 4], 4: [3], 5: []}

        def load(ids):
            return {node: graph[node] for node in ids}

        self.assertEqual(
            [r["new_nodes"] for r in breadth_first_reach(1, 3, load)["rounds"]], [2, 1, 0]
        )
        self.assertEqual(breadth_first_reach(5, 3, load)["visited_nodes"], 1)
