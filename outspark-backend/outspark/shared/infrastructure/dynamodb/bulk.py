"""IO masivo acotado; primitivas técnicas sin conocimiento de contextos."""

import base64
import hashlib
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import islice

from outspark.shared.application.errors import UseCaseError

from . import operations as db


def batches(rows, size):
    stream = iter(rows)
    while chunk := list(islice(stream, size)):
        yield chunk


def batch_get(client, table, keys, budget=None):
    return list(iter_batch_get(client, table, keys, budget))


def iter_batch_get(client, table, keys, budget=None):
    for chunk in batches(keys, 100):
        pending = {table: {"Keys": [db.encode(key) for key in chunk], "ConsistentRead": True}}
        for attempt in range(8):
            if budget is not None:
                budget["calls"] += 1
                if budget["calls"] > budget["maximum"]:
                    raise UseCaseError(
                        422, "analysis_limit", "La consulta supera el presupuesto de lectura."
                    )
            result = client.batch_get_item(RequestItems=pending, ReturnConsumedCapacity="TOTAL")
            if budget is not None:
                budget["units"] = budget.get("units", 0) + sum(
                    float(capacity.get("CapacityUnits", 0))
                    for capacity in result.get("ConsumedCapacity", [])
                )
            yield from (db.decode(item) for item in result.get("Responses", {}).get(table, []))
            pending = result.get("UnprocessedKeys", {})
            if not pending:
                break
            time.sleep(min(0.025 * 2**attempt, 1))
        else:
            raise UseCaseError(503, "unprocessed_reads", "DynamoDB dejó registros sin leer.")


def write_batch(client, table, rows):
    pending = {table: [{"PutRequest": {"Item": db.encode(row)}} for row in rows]}
    for attempt in range(12):
        result = client.batch_write_item(RequestItems=pending)
        pending = result.get("UnprocessedItems", {})
        if not pending:
            return len(rows)
        time.sleep(min(0.025 * 2**attempt, 2) + random.random() * 0.025)
    raise UseCaseError(503, "unprocessed_writes", "DynamoDB dejó registros sin escribir.")


def bulk_write(client, table, rows, *, workers=4, progress=None):
    total, waiting = 0, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for chunk in batches(rows, 25):
            waiting.append(pool.submit(write_batch, client, table, chunk))
            if len(waiting) >= workers * 2:
                total += waiting.pop(0).result()
                if progress and total % 1000 == 0:
                    progress(total)
        for future in waiting:
            total += future.result()
    if progress:
        progress(total)
    return total


def item_digest(encoded):
    def binary(value):
        if isinstance(value, (bytes, bytearray)):
            return {"base64": base64.b64encode(value).decode("ascii")}
        raise TypeError(type(value).__name__)

    data = json.dumps(encoded, sort_keys=True, separators=(",", ":"), default=binary).encode()
    return int.from_bytes(hashlib.sha256(data).digest(), "big")


class InventoryDigest:
    """Multiconjunto: suma modular de hashes SHA-256 más cardinalidad."""

    def __init__(self):
        self.count, self.total = 0, 0

    def add(self, encoded):
        self.count += 1
        self.total = (self.total + item_digest(encoded)) % 2**256

    def result(self):
        return {"items": self.count, "sha256_sum": f"{self.total:064x}"}
