from time import perf_counter

from ...domain.repositories.analyses import StructuralResultsRepository
from ...domain.services.structural import connected_components, degree_ranking


class StructuralAnalysis:
    def __init__(self, repository: StructuralResultsRepository, timer=perf_counter):
        self.repository, self.timer = repository, timer

    def execute(self, adjacency, metadata, *, should_stop=None, publish=False):
        started = self.timer()
        result = connected_components(adjacency, should_stop=should_stop)
        result["degree_ranking"] = degree_ranking(adjacency, result["group_by_node"])
        result["elapsed_seconds"] = self.timer() - started
        summary = {
            **metadata,
            "method": result["method"],
            "nodes": result["nodes"],
            "edges": result["edges"],
            "groups": len(result["groups"]),
            "visited_nodes": result["visited_nodes"],
            "complete": result["complete"],
            "elapsed_seconds": format(result["elapsed_seconds"], ".6f"),
            "degree_ranking": result["degree_ranking"][:20],
            "ranking_total_nodes": len(result["degree_ranking"]),
            "ranking_top_limit": 20,
            "interpretation": "Componentes conexas por BFS y número de vecinos directos. No representan comunidades por afinidad ni influencia observada.",
        }
        if publish and result["complete"]:
            summary = self.repository.save(metadata["dataset_id"], result, summary)
        elif publish:
            summary["publication_status"] = "withheld_incomplete"
        return {"summary": summary, "result": result}
