"""BFS por niveles y visitados, basada en Semana 5.1, páginas 12–13."""

from outspark.shared.domain.value_objects import RuleViolation


def next_layer(frontier, seen, neighbors_many):
    adjacency = neighbors_many(frontier) if frontier else {}
    following = set()
    for current in frontier:
        if current not in adjacency:
            raise RuleViolation("incomplete_graph", "Falta la adyacencia de un nodo.")
        following.update(adjacency[current])
    following.difference_update(seen)
    return following


def validate_hops(max_hops):
    if isinstance(max_hops, bool) or not isinstance(max_hops, int) or not 1 <= max_hops <= 3:
        raise RuleViolation("invalid_hops", "Usa de uno a tres saltos.")


def breadth_first_reach(seed, max_hops, neighbors_many, *, maximum_nodes=100000):
    validate_hops(max_hops)
    seen, frontier, rounds = {seed}, [seed], []
    for hop in range(1, max_hops + 1):
        following = next_layer(frontier, seen, neighbors_many)
        if len(seen) + len(following) > maximum_nodes:
            raise RuleViolation("reach_limit", "El alcance supera el máximo interactivo.")
        seen.update(following)
        rounds.append(
            {"hops": hop, "new_nodes": len(following), "total_without_seed": len(seen) - 1}
        )
        frontier = list(following)
    return {
        "seed": seed,
        "max_hops": max_hops,
        "rounds": rounds,
        "visited_nodes": len(seen),
        "complete": True,
    }
