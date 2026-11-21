"""Migración local explícita desde la tabla inicial a los seis contextos."""

import argparse
import json
from pathlib import Path

from outspark.migrations.context_tables import migrate
from outspark.persistence import configure
from outspark.shared.infrastructure.dynamodb.client import Repository, local_client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="Outspark-local")
    parser.add_argument("--endpoint", default="http://127.0.0.1:18000")
    parser.add_argument("--backup", type=Path, default=Path(".local/migration-context-tables"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--source-quiesced", action="store_true", help="La API de origen está detenida"
    )
    args = parser.parse_args()
    client = local_client(args.endpoint, read_timeout=60)
    result = migrate(
        Repository(client, args.source),
        configure(client, args.source),
        args.backup,
        resume=args.resume,
        quiesced=args.source_quiesced,
        progress=lambda status: print(json.dumps(status), flush=True),
    )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
