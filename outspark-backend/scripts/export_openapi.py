"""Exportar el contrato de los routers sin iniciar HTTP ni leer/escribir DynamoDB."""

import argparse
import json
from pathlib import Path

from outspark.bootstrap import compose, create_app
from outspark.persistence import local_storage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("local", "lambda"), default="local")
    parser.add_argument("--output", default="docs/openapi.json")
    args = parser.parse_args()
    # Composition only constructs adapters. Generating OpenAPI calls no repositories.
    storage = local_storage()
    schema = create_app(compose(storage), local_demo=args.mode == "local").openapi()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")
    operations = sum(len(methods) for methods in schema["paths"].values())
    print(f"{target}: {operations} operaciones; modo {args.mode}")


if __name__ == "__main__":
    main()
