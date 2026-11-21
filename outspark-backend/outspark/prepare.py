"""Prepara exclusivamente Docker/DynamoDB Local y datos ficticios, sin credenciales AWS."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .persistence import local_storage
from .seed import seed
from .shared.infrastructure.dynamodb.client import local_client


def prepare():
    project = Path(__file__).resolve().parents[1]
    docker = shutil.which("docker")
    if docker is None:
        # GUI-launched IDEs can inherit a PATH without Homebrew or Docker Desktop.
        docker = next(
            (
                str(path)
                for path in (
                    Path("/Applications/Docker.app/Contents/Resources/bin/docker"),
                    Path("/opt/homebrew/bin/docker"),
                    Path("/usr/local/bin/docker"),
                )
                if path.is_file() and os.access(path, os.X_OK)
            ),
            None,
        )
    if docker is None:
        raise RuntimeError(
            "Docker CLI no disponible. Instala Docker y abre su motor antes de ejecutar la API."
        )
    subprocess.run(
        [docker, "compose", "-f", str(project / "compose.yaml"), "up", "-d"],
        cwd=project,
        check=True,
    )
    client = local_client()
    for attempt in range(40):
        try:
            client.list_tables(Limit=1)
            break
        except Exception:
            if attempt == 39:
                raise RuntimeError("DynamoDB Local no respondió durante el arranque.")
            time.sleep(0.5)
    try:
        client.describe_table(TableName="Outspark-local")
    except client.exceptions.ResourceNotFoundException:
        pass
    else:
        receipt = project / ".local/migration-context-tables/verification.json"
        if not receipt.exists() or json.loads(receipt.read_text()).get("status") != "PASS":
            raise RuntimeError(
                "Existe la tabla inicial Outspark-local. Detén la API y ejecuta "
                "python -m scripts.migrate_context_tables --source-quiesced antes de preparar datos."
            )
    seed(local_storage())
    print("DynamoDB Local listo. Semilla existente conservada.", flush=True)


if __name__ == "__main__":
    prepare()
