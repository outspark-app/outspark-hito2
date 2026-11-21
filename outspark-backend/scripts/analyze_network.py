"""Offline structural analysis of the verified friendship graph; never runs in a request."""

import argparse
import json
import platform
import resource
from pathlib import Path
from time import monotonic, perf_counter

from outspark.network_analysis.application.commandservices.structural import StructuralAnalysis
from outspark.network_analysis.domain.model.dataset import DEFAULT_DATASET
from outspark.network_analysis.infrastructure.importing.source import (
    REFERENCE_HASHES,
    file_hash,
    source_rows,
)
from outspark.network_analysis.infrastructure.persistence.dynamodb.analyses import (
    DynamoStructuralResults,
)
from outspark.persistence import local_storage, postgres_local_storage
from outspark.shared.application.models import now


def induced_bfs(adjacency, limit, seed):
    if not limit or limit >= len(adjacency):
        return adjacency
    if seed not in adjacency:
        raise ValueError("El origen del piloto no está en el grafo.")
    seen, queue = {seed}, [seed]
    head = 0
    while head < len(queue) and len(seen) < limit:
        current = queue[head]
        head += 1
        for neighbor in sorted(adjacency[current]):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
                if len(seen) == limit:
                    break
    return {uid: adjacency[uid] & seen for uid in sorted(seen)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = Path(__file__).resolve().parents[2] / "outspark-facebook-grafo/facebook-links.txt.gz"
    parser.add_argument("--links", type=Path, default=source)
    parser.add_argument(
        "--nodes",
        type=int,
        default=0,
        help="0=grafo de amistades completo; otro valor=piloto BFS inducido",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--endpoint", default="http://127.0.0.1:18000")
    parser.add_argument("--table-prefix", default="Outspark-local")
    parser.add_argument("--postgres", action="store_true", help="Usar OUTSPARK_POSTGRES_DSN")
    parser.add_argument("--output", type=Path, default=Path(".local/structural-analysis.json"))
    args = parser.parse_args()
    if args.nodes < 0 or args.seconds <= 0:
        parser.error("nodes debe ser no negativo y seconds positivo.")
    if args.table_prefix != "Outspark-local" and not args.table_prefix.startswith(
        "Outspark-local-test-"
    ):
        parser.error("Prefijo local no permitido.")
    started = perf_counter()
    digest = file_hash(args.links)
    if digest != REFERENCE_HASHES["links"]:
        parser.error("El archivo no coincide con el histórico completo verificado.")
    adjacency = {}
    for _, first, second, _ in source_rows(args.links):
        adjacency.setdefault(first, set())
        adjacency.setdefault(second, set())
        if first != second:
            adjacency[first].add(second)
            adjacency[second].add(first)
    full_nodes = len(adjacency)
    adjacency = induced_bfs(adjacency, args.nodes, args.seed)
    loading_seconds = perf_counter() - started
    metadata = {
        "dataset_id": DEFAULT_DATASET,
        "source_sha256": digest,
        "algorithm_source_sha256": file_hash(
            Path(__file__).resolve().parents[1]
            / "outspark/network_analysis/domain/services/structural.py"
        ),
        "full_graph": len(adjacency) == full_nodes,
        "scope": "full_friendship_graph"
        if len(adjacency) == full_nodes
        else "bfs_induced_subgraph",
        "requested_nodes": args.nodes,
        "pilot_seed": args.seed,
        "created_at": now(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "loading_seconds": format(loading_seconds, ".6f"),
        "time_budget_seconds": str(args.seconds),
    }
    print(
        json.dumps(
            {"phase": "loaded", "nodes": len(adjacency), "loading_seconds": loading_seconds}
        ),
        flush=True,
    )
    deadline = monotonic() + args.seconds
    storage = (
        postgres_local_storage()
        if args.postgres
        else local_storage(args.endpoint, args.table_prefix)
    )
    try:
        service = StructuralAnalysis(DynamoStructuralResults(storage["network_analysis"]))
        outcome = service.execute(
            adjacency,
            metadata,
            should_stop=lambda _visited: monotonic() > deadline,
            publish=args.publish,
        )
    finally:
        if args.postgres:
            storage.close()
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    outcome["peak_process_mib"] = peak / (1024**2 if platform.system() == "Darwin" else 1024)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "phase": "finished",
                "summary": outcome["summary"],
                "peak_process_mib": outcome["peak_process_mib"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
