import random
import unittest

from outspark.network_analysis.domain.services.diffusion import compare_plans, contact_coverage
from outspark.publishing.application.queryservices.diffusion import PublicationDiffusion
from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import RuleViolation


def compare(graph, origin=1, hops=2, slots=2, custom=None):
    coverage = contact_coverage(origin, hops, lambda nodes: {node: graph[node] for node in nodes})
    return compare_plans(coverage, hops, slots, custom)


class DiffusionTests(unittest.TestCase):
    def test_greedy_deduplicates_overlapping_branches_and_custom_keeps_first_hop(self):
        graph = {
            1: [2, 3, 4],
            2: [1, 10, 11, 12, 13],
            3: [1, 10, 11, 12, 13],
            4: [1, 20, 21, 22],
            10: [2, 3],
            11: [2, 3],
            12: [2, 3],
            13: [2, 3],
            20: [4],
            21: [4],
            22: [4],
        }
        result = compare(graph, custom=[3, 4])
        self.assertEqual(result["degree"]["contacts"], [2, 3])
        self.assertEqual(result["degree"]["reachable"], 6)
        self.assertEqual(result["greedy"]["contacts"], [2, 4])
        self.assertEqual(result["greedy"]["reachable"], 9)
        self.assertEqual(result["custom"]["contacts"], [3, 4])
        self.assertEqual(result["custom"]["reachable"], 9)
        self.assertEqual([r["new_nodes"] for r in result["custom"]["rounds"]], [2, 7])
        deep = compare(graph, hops=3, slots=1, custom=[2])
        self.assertEqual([r["new_nodes"] for r in deep["custom"]["rounds"]], [1, 4, 1])
        self.assertEqual(deep["custom"]["reachable"], 6)

    def test_matches_independent_multisource_bfs_for_three_hops(self):
        rng = random.Random(21)
        for _ in range(48):
            graph = {node: [] for node in range(1, 20)}
            for a in graph:
                for b in range(a + 1, 20):
                    if rng.random() < 0.18:
                        graph[a].append(b)
                        graph[b].append(a)
            for hops in (1, 2, 3):
                options = compare(graph, hops=hops, slots=3, custom=graph[1][:2])
                for key in ("degree", "greedy", "custom"):
                    selected = options[key]["contacts"]
                    distance = {1: 0, **dict.fromkeys(selected, 1)}
                    queue = list(selected)
                    for current in queue:
                        if distance[current] == hops:
                            continue
                        for neighbor in graph[current]:
                            if neighbor not in distance:
                                distance[neighbor] = distance[current] + 1
                                queue.append(neighbor)
                    expected = [list(distance.values()).count(h) for h in range(1, hops + 1)]
                    self.assertEqual([r["new_nodes"] for r in options[key]["rounds"]], expected)
                    self.assertEqual(options[key]["reachable"], sum(expected))

    def test_isolates_empty_plan_and_invalid_contact_lists(self):
        isolated = compare({1: []}, slots=3, custom=[])
        self.assertEqual(isolated["contacts"], [])
        self.assertEqual(isolated["custom"]["reachable"], 0)
        self.assertEqual(isolated["degree"]["reachable"], 0)
        graph = {1: [2, 3], 2: [1], 3: [1]}
        for custom, slots in (([2, 2], 2), ([4], 2), ([2, 3], 1), ([1], 2)):
            with self.assertRaises(RuleViolation):
                compare(graph, custom=custom, slots=slots)
        for hops in (0, 4, True):
            with self.assertRaises(RuleViolation):
                compare(graph, hops=hops)
        for slots in (0, 11, True):
            with self.assertRaises(RuleViolation):
                compare(graph, slots=slots)

    def test_only_the_active_originals_author_can_calculate(self):
        class Publications:
            def original(self, publication_id, active=False):
                if publication_id == "retired":
                    raise RuleViolation("publication_removed", "Retirada")
                return {"author_id": "ana"}

        class Network:
            def diffusion(self, actor, **options):
                return {"origin": options["origin"]}

        service = PublicationDiffusion(Publications(), Network())
        self.assertEqual(
            service.preview("post", "ana", {"origin": 1}),
            {
                "publication_id": "post",
                "origin": 1,
            },
        )
        with self.assertRaises(UseCaseError) as foreign:
            service.preview("post", "bruno", {"origin": 1})
        self.assertEqual(foreign.exception.status, 403)
        with self.assertRaises(RuleViolation):
            service.preview("retired", "ana", {"origin": 1})
