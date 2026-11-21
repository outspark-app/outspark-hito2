"""Copy all context records from a paused DynamoDB Local demo to empty PostgreSQL tables."""

import argparse
import json
from pathlib import Path

from outspark.persistence import local_storage, postgres_local_storage


def source_records(client, table):
    pages = client.get_paginator("scan").paginate(
        TableName=table, ConsistentRead=True, PaginationConfig={"PageSize": 1000}
    )
    for page in pages:
        yield from page["Items"]


def migrate(source, target):
    source.require_tables()
    target.ensure_tables()
    inventories = {
        owner: source_records(source.client, repository.table)
        for owner, repository in source.repositories.items()
    }
    return target.client.copy_tables(inventories)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18000")
    parser.add_argument("--table-prefix", default="Outspark-local")
    parser.add_argument("--output", type=Path, default=Path(".local/postgres/migration.json"))
    args = parser.parse_args()

    source = local_storage(args.endpoint, args.table_prefix, read_timeout=60)
    target = postgres_local_storage()
    try:
        receipt = migrate(source, target)
    finally:
        target.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = json.dumps(receipt, indent=2)
    args.output.write_text(result + "\n")
    print(result)


if __name__ == "__main__":
    main()
