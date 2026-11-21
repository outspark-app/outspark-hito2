"""Compare first-hop contact plans with exact, deduplicated BFS reach."""

from dataclasses import dataclass

from outspark.shared.domain.value_objects import RuleViolation

from .reach import next_layer, validate_hops


@dataclass(frozen=True)
class ContactCoverage:
    degree: int
    rounds: tuple[int, ...]


def contact_coverage(origin, hops, neighbors_many):
    validate_hops(hops)
    contacts = sorted(set(neighbors_many([origin])[origin]) - {origin})
    adjacency = neighbors_many(contacts) if contacts else {}
    if hops == 3:
        second = next_layer(contacts, {origin, *contacts}, lambda _: adjacency)
        if second:
            adjacency.update(neighbors_many(sorted(second)))

    vertices = {origin, *contacts}.union(*adjacency.values())
    if len(contacts) * hops * len(vertices) > 256_000_000:
        raise RuleViolation("reach_limit", "El alcance supera el máximo interactivo.")
    # Dense positions keep sparse integer IDs from increasing bitmap size.
    positions = {node: i for i, node in enumerate(vertices)}

    coverage = {}
    for contact in contacts:
        frontier, seen = {contact}, {origin, contact}
        bits = bytearray((len(positions) + 7) // 8)
        rounds = []
        for hop in range(hops):
            for node in frontier:
                position = positions[node]
                bits[position // 8] |= 1 << (position % 8)
            rounds.append(int.from_bytes(bits, "little"))
            if hop + 1 < hops:
                frontier = next_layer(frontier, seen, lambda _: adjacency)
                seen.update(frontier)
        coverage[contact] = ContactCoverage(len(adjacency[contact]), tuple(rounds))
    return coverage


def automatic_contacts(coverage, slots):
    by_degree = sorted(coverage, key=lambda node: (-coverage[node].degree, node))[:slots]
    greedy, reached = [], 0
    remaining = dict(coverage)
    for _ in range(min(slots, len(remaining))):
        chosen = max(
            remaining,
            key=lambda node: ((remaining[node].rounds[-1] & ~reached).bit_count(), -node),
        )
        reached |= remaining.pop(chosen).rounds[-1]
        greedy.append(chosen)
    return by_degree, greedy


def plan(contacts, coverage, hops):
    rounds, previous = [], 0
    for hop in range(hops):
        mask = 0
        for contact in contacts:
            mask |= coverage[contact].rounds[hop]
        total = mask.bit_count()
        rounds.append({"hop": hop + 1, "new_nodes": total - previous, "total": total})
        previous = total
    return {"contacts": contacts, "reachable": previous, "rounds": rounds}


def compare_plans(coverage, hops, slots, custom):
    validate_hops(hops)
    if isinstance(slots, bool) or not isinstance(slots, int) or not 1 <= slots <= 10:
        raise RuleViolation("invalid_diffusion_slots", "Elige entre uno y diez contactos.")
    if custom is not None and (
        len(custom) > slots
        or len(set(custom)) != len(custom)
        or any(node not in coverage for node in custom)
    ):
        raise RuleViolation(
            "invalid_diffusion_contacts",
            "Elige contactos distintos del origen sin superar el número indicado.",
        )
    degree, greedy = automatic_contacts(coverage, slots)
    return {
        "contacts": [{"node_id": node, "degree": value.degree} for node, value in coverage.items()],
        "degree": plan(degree, coverage, hops),
        "greedy": plan(greedy, coverage, hops),
        "custom": plan(custom, coverage, hops) if custom is not None else None,
    }
