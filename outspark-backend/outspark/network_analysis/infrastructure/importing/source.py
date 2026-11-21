"""Preparación temporal del dataset; los archivos originales se conservan íntegros."""

import gzip
import hashlib
import itertools
import sqlite3
import tempfile
from pathlib import Path

from outspark.shared.infrastructure.dynamodb.bulk import batches

from ..persistence.dynamodb.datasets import CHUNK_SIZE, user_partition

REFERENCE_HASHES = {
    "links": "32d149f76c3421a08b03bfc629a9de6ce65b6fa56272cd9d5424e3de5b1acff2",
    "wall": "c4449336e346061068b8278d09176b195b3f132f6d6fe50adbc5730938496dca",
}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_rows(path, wall=False):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="ascii") as stream:
        for line, raw in enumerate(stream, 1):
            columns = raw.rstrip("\r\n").split("\t")
            if len(columns) != 3:
                raise ValueError(f"{path.name}:{line}: se esperaban tres columnas")
            first, second = int(columns[0]), int(columns[1])
            stamp = None if columns[2] == r"\N" else int(columns[2])
            if not 0 <= first < 10**12 or not 0 <= second < 10**12 or (wall and stamp is None):
                raise ValueError(f"{path.name}:{line}: registro no válido")
            yield line, first, second, stamp


class PreparedDataset:
    def __init__(self, dataset_id, links, wall, *, verify_reference=True):
        self.dataset_id = dataset_id
        self.files = {"links": Path(links), "wall": Path(wall)}
        hashes = {name: file_hash(path) for name, path in self.files.items()}
        if verify_reference and hashes != REFERENCE_HASHES:
            raise ValueError("Los archivos no coinciden con el dataset completo de referencia.")
        self.temporary = tempfile.TemporaryDirectory(prefix="outspark-dataset-")
        self.connection = sqlite3.connect(Path(self.temporary.name) / "source.sqlite")
        self.connection.executescript("""
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE links(line INTEGER PRIMARY KEY, owner INTEGER, peer INTEGER, stamp INTEGER);
            CREATE TABLE wall(line INTEGER PRIMARY KEY, owner INTEGER, author INTEGER, stamp INTEGER);
        """)
        for table, path in self.files.items():
            for rows in batches(source_rows(path, wall=table == "wall"), 10000):
                self.connection.executemany(f"INSERT INTO {table} VALUES(?,?,?,?)", rows)
        self.connection.executescript("""
            CREATE INDEX links_owner ON links(owner,line);
            CREATE INDEX wall_owner ON wall(owner,stamp DESC,line DESC);
            CREATE INDEX wall_author ON wall(author,stamp DESC,line DESC);
            CREATE TABLE edges(lo INTEGER,hi INTEGER,PRIMARY KEY(lo,hi)) WITHOUT ROWID;
            INSERT OR IGNORE INTO edges SELECT MIN(owner,peer),MAX(owner,peer) FROM links WHERE owner<>peer;
            CREATE TABLE adjacency(node INTEGER,neighbor INTEGER,PRIMARY KEY(node,neighbor)) WITHOUT ROWID;
            INSERT INTO adjacency SELECT lo,hi FROM edges UNION ALL SELECT hi,lo FROM edges;
            CREATE TABLE nodes(id INTEGER PRIMARY KEY,in_graph INTEGER,degree INTEGER,link_rows INTEGER,wall_received INTEGER,wall_sent INTEGER);
            INSERT INTO nodes SELECT id,1,0,0,0,0 FROM (SELECT owner AS id FROM links UNION SELECT peer FROM links);
            INSERT OR IGNORE INTO nodes SELECT id,0,0,0,0,0 FROM (SELECT owner AS id FROM wall UNION SELECT author FROM wall);
            UPDATE nodes SET degree=(SELECT COUNT(*) FROM adjacency WHERE node=nodes.id),
                link_rows=(SELECT COUNT(*) FROM links WHERE owner=nodes.id),
                wall_received=(SELECT COUNT(*) FROM wall WHERE owner=nodes.id),
                wall_sent=(SELECT COUNT(*) FROM wall WHERE author=nodes.id);
        """)

        def scalar(sql):
            return self.connection.execute(sql).fetchone()[0]

        stats = {
            "nodes": scalar("SELECT COUNT(*) FROM nodes"),
            "friendship_nodes": scalar("SELECT SUM(in_graph) FROM nodes"),
            "wall_only_nodes": scalar("SELECT COUNT(*) FROM nodes WHERE in_graph=0"),
            "friendship_rows": scalar("SELECT COUNT(*) FROM links"),
            "unique_friendships": scalar("SELECT COUNT(*) FROM edges"),
            "self_links": scalar("SELECT COUNT(*) FROM links WHERE owner=peer"),
            "dated_friendship_rows": scalar("SELECT COUNT(*) FROM links WHERE stamp IS NOT NULL"),
            "wall_events": scalar("SELECT COUNT(*) FROM wall"),
            "wall_self_events": scalar("SELECT COUNT(*) FROM wall WHERE owner=author"),
            "maximum_degree": scalar("SELECT MAX(degree) FROM nodes"),
        }
        if not stats["friendship_rows"] or not stats["wall_events"]:
            raise ValueError("El dataset no puede estar vacío.")
        if verify_reference:
            expected = {
                "nodes": 63891,
                "friendship_nodes": 63731,
                "wall_only_nodes": 160,
                "friendship_rows": 1545686,
                "unique_friendships": 817090,
                "wall_events": 876993,
            }
            if any(stats[key] != value for key, value in expected.items()):
                raise ValueError(f"Recuentos distintos de la referencia: {stats}")
        self.metadata = {
            "dataset_id": dataset_id,
            "schema_version": 1,
            "source": "MPI-SWS / Facebook New Orleans / WOSN 2009",
            "files": {
                kind: {"filename": path.name, "sha256": hashes[kind], "bytes": path.stat().st_size}
                for kind, path in self.files.items()
            },
            "counts": stats,
            "full_dataset": verify_reference,
            "interpretation": "Amistades y actividad de muro histórica; sin contenido ni cadenas observadas de republicación.",
            "chunk_size": CHUNK_SIZE,
        }

    def close(self):
        self.connection.close()
        self.temporary.cleanup()

    def node_ids(self):
        return [row[0] for row in self.connection.execute("SELECT id FROM nodes ORDER BY id")]

    def records(self):
        root = f"DATASET#{self.dataset_id}"
        for uid, in_graph, degree, links, received, sent in self.connection.execute(
            "SELECT * FROM nodes ORDER BY id"
        ):
            yield {
                "PK": root,
                "SK": f"NODE#{uid:012d}",
                "entity_type": "HISTORICAL_NODE",
                "node_id": uid,
                "in_friendship_graph": bool(in_graph),
                "degree": degree,
                "friendship_rows": links,
                "wall_received": received,
                "wall_sent": sent,
                "neighbor_chunks": (degree + CHUNK_SIZE - 1) // CHUNK_SIZE,
            }
        selections = {
            "ADJ": "SELECT node,neighbor FROM adjacency ORDER BY node,neighbor",
            "LINK": "SELECT owner,line,owner,peer,stamp FROM links ORDER BY owner,line",
            "WALL_IN": "SELECT owner,line,owner,author,stamp FROM wall ORDER BY owner,stamp DESC,line DESC",
            "WALL_OUT": "SELECT author,line,owner,author,stamp FROM wall ORDER BY author,stamp DESC,line DESC",
        }
        for kind, sql in selections.items():
            cursor = self.connection.execute(sql)
            for uid, group in itertools.groupby(cursor, lambda row: row[0]):
                payloads = (row[1] if kind == "ADJ" else list(row[1:]) for row in group)
                for part, rows in enumerate(batches(payloads, CHUNK_SIZE)):
                    yield {
                        "PK": user_partition(self.dataset_id, uid),
                        "SK": f"{kind}#{part:08d}",
                        "entity_type": "HISTORICAL_CHUNK",
                        "node_id": uid,
                        "kind": kind,
                        "rows": rows,
                    }
        for kind, path in self.files.items():
            with path.open("rb") as stream:
                for part, data in enumerate(iter(lambda: stream.read(256 * 1024), b"")):
                    yield {
                        "PK": f"{root}#SOURCE#{kind}",
                        "SK": f"BLOCK#{part:08d}",
                        "entity_type": "SOURCE_BLOCK",
                        "data": data,
                    }
