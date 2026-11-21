"""Structural results through the real HTTP boundary and temporary DynamoDB tables."""

import unittest

from outspark.bootstrap import compose_import
from outspark.network_analysis.application.commandservices.structural import StructuralAnalysis
from outspark.network_analysis.domain.model.dataset import DEFAULT_DATASET
from outspark.network_analysis.infrastructure.persistence.dynamodb.analyses import (
    DynamoStructuralResults,
)
from outspark.network_analysis.interfaces.rest.resources import (
    StructuralGroupResponse,
    StructuralSummaryResponse,
)
from tests import test_framework as framework
from tests import test_network_analysis as network

BASE = f"/api/network/datasets/{DEFAULT_DATASET}/analysis"


class StructuralAnalysisTests(unittest.TestCase):
    setUp = framework.FrameworkTests.setUp
    stop_http = framework.FrameworkTests.stop_http

    def prepare(self):
        source = network.NetworkTests.prepare_source(self)
        compose_import(self.repo).execute(source)
        results = DynamoStructuralResults(self.repo["network_analysis"])
        metadata = dict(
            dataset_id=DEFAULT_DATASET,
            source_sha256=source.metadata["files"]["links"]["sha256"],
            full_graph=True,
        )
        return results, metadata

    def get(self, suffix=""):
        return self.client.get(BASE + suffix, headers={"X-Demo-User": "ana"})

    def test_saved_analysis_serves_groups_and_excludes_wall_only_nodes(self):
        results, metadata = self.prepare()
        self.assertEqual(self.get().status_code, 404)
        graph = {1: {2}, 2: {1, 3}, 3: {2}}
        outcome = StructuralAnalysis(results).execute(graph, metadata, publish=True)
        self.assertTrue(outcome["summary"]["complete"])
        response = self.get()
        self.assertEqual(response.status_code, 200, response.text)
        summary = StructuralSummaryResponse.model_validate(response.json())
        self.assertEqual((summary.nodes, summary.edges, summary.groups), (3, 2, 1))
        group = self.get("/nodes/2")
        self.assertEqual(group.status_code, 200, group.text)
        projected = StructuralGroupResponse.model_validate(group.json())
        self.assertEqual((projected.group_id, projected.group_size, projected.degree), (1, 3, 2))
        self.assertEqual(self.get("/nodes/4").status_code, 404)
        self.assertEqual(self.client.get(BASE).status_code, 401)

    def test_budget_interruption_does_not_publish_or_claim_complete(self):
        results, metadata = self.prepare()
        outcome = StructuralAnalysis(results).execute(
            {1: {2}, 2: {1, 3}, 3: {2}}, metadata, should_stop=lambda _: True, publish=True
        )
        self.assertFalse(outcome["result"]["complete"])
        self.assertEqual(outcome["summary"]["publication_status"], "withheld_incomplete")
        self.assertEqual(self.get().status_code, 404)

    def test_wrong_source_and_partial_coverage_cannot_replace_full_results(self):
        results, metadata = self.prepare()
        graph = {1: {2}, 2: {1, 3}, 3: {2}}
        service = StructuralAnalysis(results)
        good = service.execute(graph, metadata, publish=True)["summary"]
        with self.assertRaises(ValueError):
            service.execute(graph, {**metadata, "source_sha256": "wrong"}, publish=True)
        with self.assertRaises(ValueError):
            service.execute({1: {2}, 2: {1}}, metadata, publish=True)
        self.assertEqual(self.get().json()["run_id"], good["run_id"])

    def test_derived_results_do_not_contaminate_historical_integrity_inventory(self):
        from outspark.network_analysis.infrastructure.importing.importer import (
            DynamoDatasetImporter,
        )
        from outspark.network_analysis.infrastructure.persistence.dynamodb.datasets import (
            DynamoDatasetsRepository,
        )

        source = network.NetworkTests.prepare_source(self)
        compose_import(self.repo).execute(source)
        results = DynamoStructuralResults(self.repo["network_analysis"])
        metadata = dict(
            dataset_id=DEFAULT_DATASET,
            source_sha256=source.metadata["files"]["links"]["sha256"],
            full_graph=True,
        )
        StructuralAnalysis(results).execute({1: {2}, 2: {1, 3}, 3: {2}}, metadata, publish=True)
        manifest = DynamoDatasetsRepository(self.repo["network_analysis"]).manifest(DEFAULT_DATASET)
        receipt = DynamoDatasetImporter(self.repo["network_analysis"]).verify(
            DEFAULT_DATASET, manifest["inventory"], manifest["files"]
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["counts"]["nodes"], 4)

    def test_concurrent_complete_publication_cannot_be_overwritten_by_stale_pilot(self):
        from unittest.mock import patch

        from botocore.exceptions import ClientError

        results, metadata = self.prepare()
        writer = DynamoStructuralResults(self.repo["network_analysis"])
        full_graph = {1: {2}, 2: {1, 3}, 3: {2}}
        published = []

        def stale_read(_dataset_id):
            published.append(
                StructuralAnalysis(writer).execute(full_graph, metadata, publish=True)["summary"]
            )
            return None  # Pilot observed no pointer before the full run committed.

        with patch.object(results, "latest", side_effect=stale_read):
            with self.assertRaises(ClientError) as failure:
                StructuralAnalysis(results).execute(
                    {1: {2}, 2: {1}}, {**metadata, "full_graph": False}, publish=True
                )
        self.assertEqual(
            failure.exception.response["Error"]["Code"], "TransactionCanceledException"
        )
        latest = writer.latest(DEFAULT_DATASET)
        self.assertTrue(latest["full_graph"])
        self.assertEqual(latest["run_id"], published[0]["run_id"])
