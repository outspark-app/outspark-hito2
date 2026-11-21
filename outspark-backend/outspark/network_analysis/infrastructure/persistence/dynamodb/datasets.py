import base64
import json

from outspark.shared.application.errors import UseCaseError
from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.bulk import iter_batch_get
from outspark.shared.infrastructure.dynamodb.client import cursor_decode, cursor_encode
from outspark.shared.infrastructure.dynamodb.mapping import record


KINDS = {"neighbors": "ADJ", "links": "LINK", "wall_received": "WALL_IN", "wall_sent": "WALL_OUT"}
CHUNK_SIZE = 512


def user_partition(dataset_id, uid):
    return f"DATASET#{dataset_id}#USER#{uid}"


class DynamoDatasetsRepository:
    def __init__(self, storage):
        self.storage = storage

    def manifest(self, dataset_id):
        return record(self.storage.get(f"DATASET#{dataset_id}", "MANIFEST"))

    def node(self, dataset_id, uid):
        return record(self.storage.get(f"DATASET#{dataset_id}", f"NODE#{uid:012d}"))

    def nodes(self, dataset_id, limit, cursor):
        pk, prefix = f"DATASET#{dataset_id}", "NODE#"
        rows, key = self.storage.page(pk, prefix, limit, cursor_decode(cursor, pk, prefix))
        return {"items": [record(row) for row in rows], "next_cursor": cursor_encode(key)}

    def records(self, dataset_id, uid, kind, limit, cursor):
        prefix = KINDS[kind]
        position = 0
        if cursor:
            try:
                if len(cursor) > 2000:
                    raise ValueError()
                payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
                if payload[:3] != [dataset_id, uid, kind] or len(payload) != 4:
                    raise ValueError()
                position = payload[3]
                if isinstance(position, bool) or not isinstance(position, int) or position < 0:
                    raise ValueError()
            except (ValueError, TypeError, KeyError, UnicodeDecodeError):
                raise UseCaseError(400, "invalid_cursor", "Cursor inválido para esta consulta.")
        pk, items = user_partition(dataset_id, uid), []
        while len(items) < limit:
            block, offset = divmod(position, CHUNK_SIZE)
            item = self.storage.get(pk, f"{prefix}#{block:08d}")
            if item is None:
                break
            rows = item["rows"]
            if offset >= len(rows):
                break
            take = rows[offset : offset + limit - len(items)]
            items.extend(self.present(row, kind) for row in take)
            position += len(take)
            if len(rows) < CHUNK_SIZE:
                break
        block, offset = divmod(position, CHUNK_SIZE)
        next_item = self.storage.get(pk, f"{prefix}#{block:08d}")
        has_more = bool(next_item and offset < len(next_item["rows"]))
        encoded = (
            base64.urlsafe_b64encode(json.dumps([dataset_id, uid, kind, position]).encode())
            .decode()
            .rstrip("=")
        )
        return {
            "items": items,
            "next_cursor": encoded if has_more else None,
            "dataset_id": dataset_id,
            "node_id": uid,
            "kind": kind,
        }

    @staticmethod
    def present(row, kind):
        if kind == "neighbors":
            return {"node_id": int(row)}
        if kind == "links":
            line, owner, friend, stamp = row
            return {
                "source_line": int(line),
                "owner_id": int(owner),
                "friend_id": int(friend),
                "timestamp": None if stamp is None else int(stamp),
            }
        line, owner, author, stamp = row
        return {
            "event_id": f"wall-{line}",
            "source_line": int(line),
            "wall_owner_id": int(owner),
            "author_id": int(author),
            "timestamp": int(stamp),
            "content_available": False,
        }

    def neighbors_many(self, dataset_id, nodes, budget):
        if not nodes:
            return {}
        metadata = iter_batch_get(
            self.storage.client,
            self.storage.table,
            [{"PK": f"DATASET#{dataset_id}", "SK": f"NODE#{uid:012d}"} for uid in nodes],
            budget,
        )
        degrees, keys = {}, []
        for item in metadata:
            uid = int(item["node_id"])
            degrees[uid] = int(item["degree"])
            keys.extend(
                {"PK": user_partition(dataset_id, uid), "SK": f"ADJ#{part:08d}"}
                for part in range(int(item["neighbor_chunks"]))
            )
        if len(degrees) != len(nodes):
            raise UseCaseError(503, "incomplete_graph", "Faltan nodos del dataset.")
        result = {uid: [] for uid in degrees}
        read = 0
        for chunk in iter_batch_get(self.storage.client, self.storage.table, keys, budget):
            result[int(chunk["node_id"])].extend(int(value) for value in chunk["rows"])
            read += 1
        if read != len(keys):
            raise UseCaseError(503, "incomplete_graph", "Faltan bloques de adyacencia.")
        for uid, degree in degrees.items():
            if len(result[uid]) != degree:
                raise UseCaseError(503, "incomplete_graph", "Grado y adyacencia no coinciden.")
        return result

    def guard(self, guard):
        if guard.kind != "ready_dataset":
            raise ValueError("Garantía desconocida")
        return db.check(
            self.storage.table,
            {"PK": f"DATASET#{guard.subject}", "SK": "MANIFEST"},
            "#s = :ready",
            {":ready": "READY"},
            {"#s": "status"},
        )
