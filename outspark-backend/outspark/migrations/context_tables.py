"""Copia verificable desde la tabla inicial; no modifica ni elimina el origen."""

import base64
import gzip
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import sleep
from urllib.parse import urlparse

from outspark.persistence import CONTEXTS
from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.bulk import InventoryDigest, batches, item_digest


def owner_of(item):
    """Clasificar el esquema anterior por PK+SK, nunca por USER# solamente."""
    pk, sk = item["PK"], item["SK"]
    if pk.startswith("DATASET#"):
        return "network_analysis"
    if pk.startswith("POST#") or (pk.startswith("USER#") and sk.startswith("REQUEST#")):
        return "publishing"
    if pk.startswith("FEED#") or (pk.startswith("USER#") and sk.startswith("FEED#")):
        return "discovery"
    if pk.startswith(("COMM#", "CATALOG#", "UNIQUE#COMM_NAME#")) or (
        pk.startswith("USER#") and sk.startswith("MEMBER#")
    ):
        return "communities"
    if pk.startswith("FRIEND#") or (pk.startswith("USER#") and sk.startswith("CONTACT#")):
        return "connections"
    if (pk.startswith("USER#") and sk in ("PROFILE", "PREFS")) or (pk, sk) == ("DEMO#v1", "META"):
        return "profiles"
    raise ValueError(f"Registro sin propietario conocido: {pk}/{sk}")


def scan_rows(client, table):
    args = {"TableName": table, "Limit": 500, "ConsistentRead": True}
    while True:
        result = client.scan(**args)
        yield from result["Items"]
        if not result.get("LastEvaluatedKey"):
            return
        args["ExclusiveStartKey"] = result["LastEvaluatedKey"]


def _binary(value):
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": base64.b64encode(value).decode("ascii")}
    raise TypeError(type(value).__name__)


def _restore(value):
    if set(value) == {"__bytes__"}:
        return base64.b64decode(value["__bytes__"])
    return value


def backup_rows(path):
    with gzip.open(path, "rt") as source:
        for line in source:
            yield json.loads(line, object_hook=_restore)


def _save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def _copy_batch(client, target, rows):
    pending = {}
    for row in rows:
        table = target[owner_of({"PK": row["PK"]["S"], "SK": row["SK"]["S"]})].table
        pending.setdefault(table, []).append({"PutRequest": {"Item": row}})
    for attempt in range(12):
        pending = client.batch_write_item(RequestItems=pending).get("UnprocessedItems", {})
        if not pending:
            return len(rows)
        sleep(min(0.025 * 2**attempt, 2))
    raise RuntimeError("Escrituras pendientes; reanuda desde la copia")


def migrate(source, target, directory, *, resume=False, quiesced=False, progress=None):
    if not quiesced:
        raise ValueError("Detén las escrituras del origen antes de migrar")
    endpoint = urlparse(source.client.meta.endpoint_url)
    if endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Esta migración está habilitada exclusivamente en DynamoDB Local")
    if source.client is not target.client:
        raise ValueError("Origen y destino deben utilizar el mismo cliente local")
    if source.table != "Outspark-local" and not source.table.startswith("Outspark-local-test-"):
        raise ValueError("Origen local no permitido")
    expected_names = {owner: source.table + "-" + owner.replace("_", "-") for owner in CONTEXTS}
    if {owner: repo.table for owner, repo in target.repositories.items()} != expected_names:
        raise ValueError("Los destinos deben corresponder al prefijo del origen")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path, archive = directory / "source.json", directory / "source.jsonl.gz"
    index_path = directory / "expected.sqlite"
    if manifest_path.exists():
        if not resume:
            raise ValueError("La copia de seguridad ya existe; utiliza --resume")
        expected = json.loads(manifest_path.read_text())
        if expected["source"] != source.table or expected["tables"] != expected_names:
            raise ValueError("La copia pertenece a otro entorno")
    else:
        if archive.exists() or index_path.exists():
            raise ValueError(
                "Copia inicial incompleta; conserva los archivos y usa un directorio nuevo"
            )
        total = InventoryDigest()
        inventories = {owner: InventoryDigest() for owner in CONTEXTS}
        with sqlite3.connect(index_path) as index, gzip.open(archive, "wt") as output:
            index.execute("CREATE TABLE expected(owner, pk, sk, digest, PRIMARY KEY(owner,pk,sk))")
            for row in scan_rows(source.client, source.table):
                decoded = db.decode(row)
                owner = owner_of(decoded)
                index.execute(
                    "INSERT INTO expected VALUES (?,?,?,?)",
                    (owner, decoded["PK"], decoded["SK"], f"{item_digest(row):064x}"),
                )
                output.write(json.dumps(row, default=_binary, separators=(",", ":")) + "\n")
                total.add(row)
                inventories[owner].add(row)
                if progress and total.count % 10000 == 0:
                    progress({"phase": "backup", "items": total.count})
        expected = {
            "source": source.table,
            "tables": expected_names,
            "inventory": total.result(),
            "contexts": {owner: inventory.result() for owner, inventory in inventories.items()},
        }
        _save(manifest_path, expected)

    # A damaged backup is rejected before any destination write, including on resume.
    total = InventoryDigest()
    for row in backup_rows(archive):
        total.add(row)
    if total.result() != expected["inventory"]:
        raise ValueError("La copia de seguridad no corresponde al inventario")
    target.ensure_tables()
    with sqlite3.connect(index_path) as index:
        for owner, repository in target.repositories.items():
            for row in scan_rows(source.client, repository.table):
                item = db.decode(row)
                match = index.execute(
                    "SELECT digest FROM expected WHERE owner=? AND pk=? AND sk=?",
                    (owner, item["PK"], item["SK"]),
                ).fetchone()
                if not resume or match is None or match[0] != f"{item_digest(row):064x}":
                    raise ValueError(
                        "El destino contiene datos ajenos o modificados; no se sobrescriben"
                    )

    # Raw SDK attributes preserve exact values, timestamps, IDs and binary archives.
    written = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        waiting = []
        for rows in batches(backup_rows(archive), 25):
            waiting.append(pool.submit(_copy_batch, source.client, target, rows))
            if len(waiting) >= 8:
                written += waiting.pop(0).result()
                if progress and written % 10000 == 0:
                    progress({"phase": "copy", "items": written})
        for future in waiting:
            written += future.result()

    actual = {}
    for owner, repository in target.repositories.items():
        inventory = InventoryDigest()
        for row in scan_rows(source.client, repository.table):
            if owner_of(db.decode(row)) != owner:
                raise ValueError("Registro en un contexto incorrecto")
            inventory.add(row)
            if progress and inventory.count % 10000 == 0:
                progress({"phase": "verify", "context": owner, "items": inventory.count})
        actual[owner] = inventory.result()
    if actual != expected["contexts"]:
        raise ValueError("El inventario de destino no coincide con el origen")
    original = InventoryDigest()
    for row in scan_rows(source.client, source.table):
        original.add(row)
        if progress and original.count % 10000 == 0:
            progress({"phase": "verify_source", "items": original.count})
    if original.result() != expected["inventory"]:
        raise ValueError("El origen cambió durante la migración; no cambies la API")
    result = {"status": "PASS", **expected, "verified_contexts": actual, "source_unchanged": True}
    _save(directory / "verification.json", result)
    return result
