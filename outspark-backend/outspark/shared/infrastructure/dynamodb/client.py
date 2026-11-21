"""Acceso DynamoDB por claves; límites explícitos y sin Scan."""

import base64
import json
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config

from outspark.shared.application.errors import UseCaseError as ApiError

from . import operations as db


def local_client(endpoint="http://127.0.0.1:18000", *, read_timeout=5):
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("DynamoDB Local debe estar en HTTP loopback")
    return boto3.client(
        "dynamodb",
        endpoint_url=endpoint,
        region_name="us-east-2",
        aws_access_key_id="outsparkLocal",
        aws_secret_access_key="outsparkLocal",
        config=Config(
            retries={"max_attempts": 2, "mode": "standard"},
            connect_timeout=2,
            read_timeout=read_timeout,
        ),
    )


class Repository:
    def __init__(self, client, table, *, schema="table.json"):
        self.client, self.table, self.schema = client, table, schema

    def get(self, pk, sk):
        return db.get(self.client, self.table, pk, sk)

    def ensure_table(self):
        try:
            self.client.describe_table(TableName=self.table)
        except self.client.exceptions.ResourceNotFoundException:
            config = json.loads((Path(__file__).with_name(self.schema)).read_text())
            config["TableName"] = self.table
            self.client.create_table(**config)
            self.client.get_waiter("table_exists").wait(TableName=self.table)

    def page(self, pk, prefix="", limit=20, cursor=None, index=None, budget=None):
        if budget and not budget.take():
            return [], cursor
        partition, sort = (
            ("PK", "SK")
            if not index
            else (("GSI1PK", "GSI1SK") if index == "ActivityByActor" else ("GSI2PK", "GSI2SK"))
        )
        args = dict(
            TableName=self.table,
            KeyConditionExpression="#pk = :pk",
            ExpressionAttributeNames={"#pk": partition},
            ExpressionAttributeValues=db.encode({":pk": pk}),
            Limit=limit,
            ScanIndexForward=not bool(index),
            ReturnConsumedCapacity="TOTAL",
        )
        if prefix:
            args["KeyConditionExpression"] += " AND begins_with(#sk, :prefix)"
            args["ExpressionAttributeNames"]["#sk"] = sort
            args["ExpressionAttributeValues"].update(db.encode({":prefix": prefix}))
        if index:
            args["IndexName"] = index
        else:
            args["ConsistentRead"] = True
        if cursor:
            args["ExclusiveStartKey"] = cursor
        result = self.client.query(**args)
        if budget:
            budget.units += float(result.get("ConsumedCapacity", {}).get("CapacityUnits", 0))
        return [db.decode(i) for i in result["Items"]], result.get("LastEvaluatedKey")

    def window(self, pk, prefix="", limit=20, index=None, budget=None):
        items, cursor = [], None
        while len(items) < limit:
            if budget and budget.pages >= budget.maximum:
                budget.truncated = True
                break
            page, cursor = self.page(pk, prefix, min(20, limit - len(items)), cursor, index, budget)
            items.extend(page)
            if not cursor:
                break
        if cursor and budget:
            budget.truncated = True
        if budget:
            budget.windows.append(
                {
                    "partition": pk,
                    "prefix": prefix,
                    "index": index,
                    "count": len(items),
                    "next_cursor": cursor_encode(cursor),
                }
            )
        return items


def cursor_encode(key):
    return base64.urlsafe_b64encode(json.dumps(key).encode()).decode().rstrip("=") if key else None


def cursor_decode(value, pk, prefix):
    if not value:
        return None
    try:
        if len(value) > 2000:
            raise ValueError()
        key = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        if (
            set(key) != {"PK", "SK"}
            or key["PK"] != {"S": pk}
            or not key["SK"]["S"].startswith(prefix)
        ):
            raise ValueError()
        return key
    except (ValueError, KeyError, TypeError):
        raise ApiError(400, "invalid_cursor", "Cursor inválido para esta consulta.")
