"""Importación explícita y verificable del dataset en el almacenamiento local."""

import argparse
import json
import logging
from pathlib import Path

from outspark.bootstrap import compose_import
from outspark.network_analysis.domain.model.dataset import DEFAULT_DATASET
from outspark.network_analysis.infrastructure.importing.source import PreparedDataset
from outspark.persistence import local_storage, postgres_local_storage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    graph = Path(__file__).resolve().parents[2] / "outspark-facebook-grafo"
    parser.add_argument("--links", type=Path, default=graph / "facebook-links.txt.gz")
    parser.add_argument("--wall", type=Path, default=graph / "facebook-wall.txt.gz")
    parser.add_argument("--endpoint", default="http://127.0.0.1:18000")
    parser.add_argument("--table-prefix", default="Outspark-local")
    parser.add_argument("--postgres", action="store_true", help="Usar OUTSPARK_POSTGRES_DSN")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.table_prefix != "Outspark-local" and not args.table_prefix.startswith(
        "Outspark-local-test-"
    ):
        parser.error("Solo se permiten Outspark-local o tablas locales de prueba.")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.postgres and args.output is None:
        args.output = Path(".local/postgres/importacion_dataset.json")
    elif args.output is None:
        args.output = Path(".local/importacion_dataset.json")
    storage = (
        postgres_local_storage()
        if args.postgres
        else local_storage(args.endpoint, args.table_prefix, read_timeout=60)
    )
    try:
        import_dataset(args, storage)
    finally:
        if args.postgres:
            storage.close()


def import_dataset(args, storage):
    storage.ensure_tables()
    print("Preparando los dos archivos completos y comprobando hashes...", flush=True)
    source = PreparedDataset(DEFAULT_DATASET, args.links, args.wall)
    try:
        print(json.dumps({"phase": "prepared", **source.metadata["counts"]}), flush=True)
        importer = compose_import(
            storage,
            workers=args.workers,
            progress=lambda count: print(
                json.dumps({"phase": "written", "items": count}), flush=True
            ),
        )
        result = importer.execute(source, resume=args.resume)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=int) + "\n")
        print(
            json.dumps(
                {
                    "phase": "READY",
                    "counts": source.metadata["counts"],
                    "inventory": result["inventory"],
                    "profiles": result["profiles"],
                    "replayed": result.get("replayed", False),
                    "output": str(args.output),
                },
                default=int,
            ),
            flush=True,
        )
    finally:
        source.close()


if __name__ == "__main__":
    main()
