"""Configuración de almacenamiento en la raíz de composición, fuera del dominio."""

import os
import re
from dataclasses import dataclass

import boto3
from psycopg.conninfo import conninfo_to_dict

from .shared.infrastructure.dynamodb.client import Repository, local_client
from .shared.infrastructure.postgres.records import PostgresRecords

CONTEXTS = ("profiles", "connections", "communities", "publishing", "discovery", "network_analysis")


@dataclass(frozen=True)
class Persistence:
    client: object
    repositories: dict[str, Repository]

    def __getitem__(self, owner):
        return self.repositories[owner]

    def ensure_tables(self):
        for repository in self.repositories.values():
            repository.ensure_table()

    def require_tables(self):
        for repository in self.repositories.values():
            self.client.describe_table(TableName=repository.table)


class PostgresPersistence(Persistence):
    def ensure_tables(self):
        self.client.ensure_schema()

    def require_tables(self):
        self.client.require_schema()

    def close(self):
        self.client.close()


def postgres_local_storage(dsn=None, *, schema=None):
    dsn = dsn or os.environ.get("OUTSPARK_POSTGRES_DSN")
    if not dsn:
        raise ValueError("Falta OUTSPARK_POSTGRES_DSN")
    config = conninfo_to_dict(dsn)
    host = config.get("host", "")
    if (
        not (host in ("127.0.0.1", "::1", "localhost") or host.startswith("/"))
        or "," in host
        or config.get("service")
        or config.get("hostaddr")
    ):
        raise ValueError("La demo PostgreSQL requiere un socket local o una dirección loopback")
    return postgres_storage(dsn, schema=schema)


def postgres_storage(dsn, *, schema=None):
    schema = schema or os.environ.get("OUTSPARK_POSTGRES_SCHEMA", "outspark")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
        raise ValueError("Esquema PostgreSQL inválido")
    client = PostgresRecords(dsn, schema, CONTEXTS, indexed_table="publishing")
    return PostgresPersistence(client, {owner: Repository(client, owner) for owner in CONTEXTS})


def configure(client, prefix):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,220}", prefix):
        raise ValueError("Prefijo DynamoDB inválido")
    return Persistence(
        client,
        {
            owner: Repository(
                client,
                prefix + "-" + owner.replace("_", "-"),
                schema="table.json" if owner == "publishing" else "base-table.json",
            )
            for owner in CONTEXTS
        },
    )


def local_storage(endpoint="http://127.0.0.1:18000", prefix="Outspark-local", *, read_timeout=5):
    if prefix != "Outspark-local" and not re.fullmatch(r"Outspark-local-test-[a-z0-9-]+", prefix):
        raise ValueError("Solo se permiten el entorno local o entornos desechables de prueba")
    return configure(local_client(endpoint, read_timeout=read_timeout), prefix)


def cloud_storage():
    # Provisioning is explicit infrastructure work, never part of a Lambda cold start.
    prefix = os.environ["OUTSPARK_TABLE_PREFIX"]
    return configure(boto3.client("dynamodb"), prefix)
