"""PostgreSQL implementation of the record operations used by Outspark's repositories."""

import base64
import json
from collections.abc import Mapping
from contextlib import contextmanager

from botocore.exceptions import ClientError
from psycopg import Error, errors, sql
from psycopg_pool import ConnectionPool, PoolTimeout

from ..dynamodb.bulk import InventoryDigest
from ..dynamodb.operations import DES

KEYS = ("PK", "SK")
INDEXES = {
    "ActivityByActor": ("GSI1PK", "GSI1SK"),
    "PublicationsByCommunity": ("GSI2PK", "GSI2SK"),
}
COLUMNS = ("pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk")
FIELDS = (*KEYS, *INDEXES["ActivityByActor"], *INDEXES["PublicationsByCommunity"])
DATASET_FILTER = (
    "(PK = :root AND begins_with(SK, :node)) OR "
    "begins_with(PK, :users) OR begins_with(PK, :sources)"
)


def storage_error(code):
    return ClientError(
        {"Error": {"Code": code, "Message": "PostgreSQL record operation failed"}},
        "PostgreSQL",
    )


def binary_to_json(value):
    if isinstance(value, (bytes, bytearray)):
        return {"__outspark_bytes__": base64.b64encode(value).decode("ascii")}
    raise TypeError(type(value).__name__)


def json_to_binary(value):
    marker = value.get("__outspark_bytes__")
    if len(value) == 1 and isinstance(marker, str):
        return base64.b64decode(marker, validate=True)
    return value


def dump_record(value):
    return json.dumps(value, default=binary_to_json, separators=(",", ":"))


def load_record(raw):
    return json.loads(raw, object_hook=json_to_binary)


def record_values(item):
    keys = tuple(item.get(field, {}).get("S") for field in FIELDS)
    return (*keys, dump_record(item))


def key_values(item, fields=KEYS):
    return tuple(item[field]["S"] for field in fields)


def prefix_pattern(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def condition_matches(expression, item, names, values):
    """Only the conjunctions of existence and equality produced by the repositories."""
    for term in expression.split(" AND "):
        if term == "attribute_exists(PK)":
            if item is None:
                return False
            continue
        field, separator, token = term.partition(" = ")
        if not separator or token not in values:
            raise ValueError("Condición de persistencia no soportada")
        path = [names.get(part, part) for part in field.split(".")]
        attribute = (item or {}).get(path[0])
        for part in path[1:]:
            attribute = (attribute or {}).get("M", {}).get(part)
        expected = values[token]
        if (
            attribute is None
            or attribute.keys() != expected.keys()
            or DES.deserialize(attribute) != DES.deserialize(expected)
        ):
            return False
    return True


class PostgresRecords:
    """Keep existing record keys and atomic guards while storing each context in its own table."""

    def __init__(self, dsn, schema, tables, indexed_table):
        self.schema = schema
        self.tables = frozenset(tables)
        self.indexed_table = indexed_table
        self.pool = ConnectionPool(
            dsn, min_size=0, max_size=5, timeout=8, open=False, kwargs={"connect_timeout": 5}
        )
        self.pool.open()

    def close(self):
        self.pool.close()

    def table(self, name):
        if name not in self.tables:
            raise ValueError("Contexto de persistencia desconocido")
        return sql.Identifier(self.schema, name)

    @contextmanager
    def connection(self):
        try:
            with self.pool.connection() as connection:
                yield connection
        except (errors.SerializationFailure, errors.DeadlockDetected) as exc:
            raise storage_error("TransactionCanceledException") from exc
        except (Error, PoolTimeout) as exc:
            raise storage_error("StorageUnavailable") from exc

    def ensure_schema(self):
        with self.connection() as connection:
            # DDL creation is explicit and safe when two setup commands start together.
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (self.schema,))
            connection.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema))
            )
            for name in sorted(self.tables):
                connection.execute(
                    sql.SQL("""
                        CREATE TABLE IF NOT EXISTS {} (
                            pk text COLLATE "C" NOT NULL, sk text COLLATE "C" NOT NULL,
                            gsi1pk text COLLATE "C", gsi1sk text COLLATE "C",
                            gsi2pk text COLLATE "C", gsi2sk text COLLATE "C",
                            item json NOT NULL,
                            PRIMARY KEY (pk, sk)
                        )
                    """).format(self.table(name))
                )
            for index, columns in INDEXES.items():
                connection.execute(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {} ON {} ({}, {}, pk, sk) WHERE {} IS NOT NULL"
                    ).format(
                        sql.Identifier("publishing_" + index.lower()),
                        self.table(self.indexed_table),
                        *(sql.Identifier(column.lower()) for column in (*columns, columns[0])),
                    )
                )

    def require_schema(self):
        with self.connection() as connection:
            for name in sorted(self.tables):
                connection.execute(
                    sql.SQL(
                        "SELECT pk, sk, gsi1pk, gsi1sk, gsi2pk, gsi2sk, item FROM {} LIMIT 0"
                    ).format(self.table(name))
                )

    def _read(self, connection, name, key, *, lock=False):
        query = sql.SQL("SELECT item::text FROM {} WHERE pk = %s AND sk = %s").format(
            self.table(name)
        )
        if lock:
            query += sql.SQL(" FOR UPDATE")
        row = connection.execute(query, key_values(key)).fetchone()
        return load_record(row[0]) if row else None

    def get_item(self, *, TableName, Key, ConsistentRead=False):
        with self.connection() as connection:
            item = self._read(connection, TableName, Key)
        return {"Item": item} if item is not None else {}

    @staticmethod
    def _page(records, limit, fields):
        page = [load_record(row[0]) for row in records[:limit]]
        data = {"Items": page}
        if len(records) > limit:
            data["LastEvaluatedKey"] = {field: page[-1][field] for field in fields}
        return data

    def query(
        self,
        *,
        TableName,
        KeyConditionExpression,
        ExpressionAttributeValues,
        ExpressionAttributeNames=None,
        Limit=500,
        IndexName=None,
        ScanIndexForward=True,
        ExclusiveStartKey=None,
        ConsistentRead=False,
        ReturnConsumedCapacity=None,
    ):
        partition, sort = INDEXES[IndexName] if IndexName else KEYS
        names = ExpressionAttributeNames or {}
        field, _, prefix_term = KeyConditionExpression.partition(" AND ")
        key, sep, token = field.partition(" = ")
        if not sep or names.get(key, key) != partition or token != ":pk":
            raise ValueError("Partición de persistencia no soportada")
        if prefix_term and prefix_term not in (
            f"begins_with({sort}, :prefix)",
            "begins_with(#sk, :prefix)",
        ):
            raise ValueError("Prefijo de persistencia no soportado")
        partition_column, sort_column = map(sql.Identifier, (partition.lower(), sort.lower()))
        query = sql.SQL("SELECT item::text FROM {} WHERE {} = %s").format(
            self.table(TableName), partition_column
        )
        parameters = [ExpressionAttributeValues[":pk"]["S"]]
        if prefix_term:
            query += sql.SQL(" AND {} LIKE %s").format(sort_column)
            parameters.append(prefix_pattern(ExpressionAttributeValues[":prefix"]["S"]))
        order_fields = (sort, *KEYS) if IndexName else (sort,)
        order_columns = [sql.Identifier(field.lower()) for field in order_fields]
        direction = sql.SQL(" ASC") if ScanIndexForward else sql.SQL(" DESC")
        if ExclusiveStartKey:
            comparator = sql.SQL(">") if ScanIndexForward else sql.SQL("<")
            query += sql.SQL(" AND ({}) {} ({})").format(
                sql.SQL(", ").join(order_columns),
                comparator,
                sql.SQL(", ").join(sql.Placeholder() * len(order_columns)),
            )
            parameters.extend(key_values(ExclusiveStartKey, order_fields))
        query += sql.SQL(" ORDER BY {} LIMIT %s").format(
            sql.SQL(", ").join(column + direction for column in order_columns)
        )
        with self.connection() as connection:
            rows = connection.execute(query, (*parameters, Limit + 1)).fetchall()
        return self._page(rows, Limit, (*KEYS, partition, sort) if IndexName else KEYS)

    def scan(
        self,
        *,
        TableName,
        FilterExpression,
        ExpressionAttributeValues,
        Limit,
        ExclusiveStartKey=None,
        ConsistentRead=False,
    ):
        if FilterExpression != DATASET_FILTER:
            raise ValueError("Verificación de inventario no soportada")
        values = ExpressionAttributeValues
        query = sql.SQL("""
            SELECT item::text FROM {}
            WHERE ((pk = %s AND sk LIKE %s) OR pk LIKE %s OR pk LIKE %s)
        """).format(self.table(TableName))
        params = [values[":root"]["S"]]
        params.extend(prefix_pattern(values[key]["S"]) for key in (":node", ":users", ":sources"))
        if ExclusiveStartKey:
            query += sql.SQL(" AND (pk, sk) > (%s, %s)")
            params.extend(key_values(ExclusiveStartKey))
        query += sql.SQL(" ORDER BY pk, sk LIMIT %s")
        with self.connection() as connection:
            rows = connection.execute(query, (*params, Limit + 1)).fetchall()
        return self._page(rows, Limit, KEYS)

    def batch_get_item(self, *, RequestItems, ReturnConsumedCapacity=None):
        responses = {}
        with self.connection() as connection:
            for name, request in RequestItems.items():
                keys = [key_values(key) for key in request["Keys"]]
                if not keys:
                    responses[name] = []
                    continue
                pks, sks = map(list, zip(*keys))
                rows = connection.execute(
                    sql.SQL("""
                        SELECT item::text FROM {}
                        WHERE (pk, sk) IN (SELECT * FROM unnest(%s::text[], %s::text[]))
                    """).format(self.table(name)),
                    (pks, sks),
                )
                responses[name] = [load_record(row[0]) for row in rows]
        return {"Responses": responses}

    def _insert_statement(self, name, *, insert_only=False):
        statement = sql.SQL("INSERT INTO {} ({}, item) VALUES (%s, %s, %s, %s, %s, %s, %s::json)")
        statement = statement.format(
            self.table(name), sql.SQL(", ").join(map(sql.Identifier, COLUMNS))
        )
        if insert_only:
            return statement + sql.SQL(" ON CONFLICT (pk, sk) DO NOTHING")
        return statement + sql.SQL("""
            ON CONFLICT (pk, sk) DO UPDATE SET
                gsi1pk = EXCLUDED.gsi1pk, gsi1sk = EXCLUDED.gsi1sk,
                gsi2pk = EXCLUDED.gsi2pk, gsi2sk = EXCLUDED.gsi2sk, item = EXCLUDED.item
        """)

    def batch_write_item(self, *, RequestItems):
        with self.connection() as connection, connection.cursor() as cursor:
            for name, requests in sorted(RequestItems.items()):
                items = sorted(
                    (request["PutRequest"]["Item"] for request in requests), key=key_values
                )
                cursor.executemany(self._insert_statement(name), map(record_values, items))
        return {}

    def _apply(self, connection, kind, operation, conflict_code):
        table = operation["TableName"]
        condition = operation.get("ConditionExpression")
        if kind == "Put" and condition in (None, "attribute_not_exists(PK)"):
            insert_only = condition is not None
            result = connection.execute(
                self._insert_statement(table, insert_only=insert_only),
                record_values(operation["Item"]),
            )
            if result.rowcount == 0:
                raise storage_error(conflict_code)
            return
        key = operation["Item"] if kind == "Put" else operation["Key"]
        old = self._read(connection, table, key, lock=True)
        names = operation.get("ExpressionAttributeNames", {})
        values = operation.get("ExpressionAttributeValues", {})
        if not condition_matches(condition, old, names, values):
            raise storage_error(conflict_code)
        if kind == "ConditionCheck":
            return
        if kind == "Update":
            assignment = operation["UpdateExpression"].removeprefix("SET ")
            field, token = assignment.split(" = ")
            item = {**old, names.get(field, field): values[token]}
        elif kind == "Put":
            item = operation["Item"]
        else:
            raise ValueError("Escritura de persistencia no soportada")
        connection.execute(self._insert_statement(table), record_values(item))

    def put_item(self, **operation):
        with self.connection() as connection:
            self._apply(connection, "Put", operation, "ConditionalCheckFailedException")
        return {}

    def transact_write_items(self, *, TransactItems):
        operations = [next(iter(action.items())) for action in TransactItems]

        def lock_order(pair):
            kind, operation = pair
            item = operation["Item"] if kind == "Put" else operation["Key"]
            return (operation["TableName"], *key_values(item))

        with self.connection() as connection:
            for kind, operation in sorted(operations, key=lock_order):
                self._apply(connection, kind, operation, "TransactionCanceledException")
        return {}

    def copy_tables(self, inventories: Mapping):
        """Load a quiescent source into an empty target in one SQL transaction."""
        with self.connection() as connection:
            receipts = {}
            for name, items in sorted(inventories.items()):
                table = self.table(name)
                connection.execute(sql.SQL("LOCK TABLE {} IN EXCLUSIVE MODE").format(table))
                if connection.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(table)).fetchone():
                    raise ValueError(f"La tabla destino {name} ya contiene datos.")
                command = sql.SQL("COPY {} ({}, item) FROM STDIN").format(
                    table, sql.SQL(", ").join(map(sql.Identifier, COLUMNS))
                )
                expected = InventoryDigest()
                with connection.cursor().copy(command) as copy:
                    for item in items:
                        expected.add(item)
                        copy.write_row(record_values(item))
                actual = InventoryDigest()
                with connection.cursor(name="outspark_inventory") as rows:
                    rows.execute(sql.SQL("SELECT item::text FROM {}").format(table))
                    for row in rows:
                        actual.add(load_record(row[0]))
                if actual.result() != expected.result():
                    raise ValueError(f"El inventario migrado de {name} no coincide.")
                receipts[name] = actual.result()
            return receipts
