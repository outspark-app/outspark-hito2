"""BFS components checked against the weighted QuickUnion taught in week 6–7."""

import random
import unittest

from outspark.network_analysis.domain.services.structural import (
    METHOD,
    InvalidGraphError,
    connected_components,
    degree_ranking,
)


def ufds_partition(graph):
    labels = list(graph)
    index = {node: i for i, node in enumerate(labels)}
    parent = [-1] * len(labels)

    def find(i):
        while parent[i] >= 0:
            i = parent[i]
        return i

    for node, neighbors in graph.items():
        for neighbor in neighbors:
            a, b = find(index[node]), find(index[neighbor])
            if a != b:
                if parent[a] > parent[b]:
                    a, b = b, a
                parent[a] += parent[b]
                parent[b] = a
    groups = {}
    for i, node in enumerate(labels):
        groups.setdefault(find(i), set()).add(node)
    return {frozenset(group) for group in groups.values()}


class ComponentsTests(unittest.TestCase):
    def test_components_cycles_isolates_and_degree(self):
        graph = {1: {2, 3}, 2: {1, 3}, 3: {1, 2}, 4: set(), 7: {8}, 8: {7}}
        result = connected_components(graph)
        self.assertEqual(result["method"], METHOD)
        self.assertEqual((result["nodes"], result["edges"]), (6, 4))
        self.assertTrue(result["complete"])
        self.assertEqual(result["group_by_node"], {1: 1, 2: 1, 3: 1, 4: 4, 7: 7, 8: 7})
        ranking = degree_ranking(graph, result["group_by_node"])
        self.assertEqual([r["node_id"] for r in ranking], [1, 2, 3, 7, 8, 4])
        self.assertEqual(ranking[0]["degree"], 2)
        self.assertNotIn("modularity", result)

    def test_random_graphs_match_course_ufds(self):
        generator = random.Random(21)
        for n in range(25):
            for _ in range(20):
                graph = {i: set() for i in range(n)}
                for u in range(n):
                    for v in range(u + 1, n):
                        if generator.random() < 0.1:
                            graph[u].add(v)
                            graph[v].add(u)
                actual = connected_components(graph)
                self.assertEqual({frozenset(g) for g in actual["groups"]}, ufds_partition(graph))
                self.assertEqual(actual["visited_nodes"], n)
                self.assertEqual(actual["edges"], sum(map(len, graph.values())) // 2)
                for node, neighbors in graph.items():
                    for neighbor in neighbors:
                        self.assertEqual(
                            actual["group_by_node"][node], actual["group_by_node"][neighbor]
                        )

    def test_lists_and_input_order_preserve_labels(self):
        graph = {7: [9], 9: [7], 1: []}
        saved = {node: list(neighbors) for node, neighbors in graph.items()}
        first = connected_components(graph)
        second = connected_components(dict(reversed(list(graph.items()))))
        self.assertEqual(first["group_by_node"], second["group_by_node"])
        self.assertEqual(graph, saved)

    def test_long_chain_avoids_recursion_limit(self):
        graph = {i: set() for i in range(3000)}
        for i in range(2999):
            graph[i].add(i + 1)
            graph[i + 1].add(i)
        result = connected_components(graph)
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["visited_nodes"], 3000)

    def test_empty_and_interruption(self):
        self.assertTrue(connected_components({})["complete"])
        result = connected_components({1: {2}, 2: {1}}, should_stop=lambda _: True)
        self.assertFalse(result["complete"])
        self.assertEqual(result["group_by_node"], {})
        self.assertEqual(result["visited_nodes"], 0)
        self.assertEqual(degree_ranking({1: {2}, 2: {1}}, {}), [])

    def test_invalid_graphs(self):
        for graph in [
            None,
            {True: set()},
            {1: {1}},
            {1: {2}},
            {1: {2}, 2: set()},
            {1: [2, 2], 2: [1]},
            {1: {False}},
            {1: "neighbors"},
        ]:
            with self.subTest(graph=graph), self.assertRaises(InvalidGraphError):
                connected_components(graph)
        with self.assertRaises(TypeError):
            connected_components({}, should_stop=3)


class QueryMethodTests(unittest.TestCase):
    def test_old_method_is_rejected_for_summary_and_membership(self):
        from types import SimpleNamespace

        from outspark.network_analysis.application.queryservices.structural import StructuralQueries
        from outspark.shared.application.errors import UseCaseError

        latest = {"method": "retired-method/1", "source_sha256": "same-hash"}
        results = SimpleNamespace(latest=lambda _: latest)
        datasets = SimpleNamespace(
            manifest=lambda _: {"status": "READY", "files": {"links": {"sha256": "same-hash"}}}
        )
        service = StructuralQueries(results, datasets)
        for operation in [
            lambda: service.summary("facebook-wosn2009"),
            lambda: service.group("facebook-wosn2009", 1),
        ]:
            with self.assertRaises(UseCaseError) as error:
                operation()
            self.assertIn("analysis_method_stale", str(error.exception.__dict__))

    def test_ranking_keeps_every_node_for_persistence(self):
        graph = {i: set() for i in range(35)}
        partition = connected_components(graph)
        ranking = degree_ranking(graph, partition["group_by_node"])
        self.assertEqual(len(ranking), 35)
        self.assertEqual(ranking[-1], {"node_id": 34, "group_id": 34, "degree": 0})
