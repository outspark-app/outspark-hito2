"""Primitivas técnicas de DynamoDB; ninguna regla de otro contexto."""
import hashlib
import json
import re
from uuid import uuid4
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from botocore.exceptions import ClientError

SER, DES = TypeSerializer(), TypeDeserializer()


def encode(item):
    return {key: SER.serialize(value) for key, value in item.items()}


def decode(item):
    return {key: DES.deserialize(value) for key, value in item.items()}


def digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def get(client, table, pk, sk):
    item = client.get_item(TableName=table, Key=encode({'PK': pk, 'SK': sk}),
                           ConsistentRead=True).get('Item')
    return decode(item) if item else None


def query(client, table, pk, prefix):
    """Query paginada sobre tabla base, con lectura fuerte. No hace Scan."""
    args = dict(TableName=table, KeyConditionExpression='PK = :pk AND begins_with(SK, :prefix)',
                ExpressionAttributeValues=encode({':pk': pk, ':prefix': prefix}),
                ConsistentRead=True)
    result = []
    while True:
        page = client.query(**args)
        result.extend(decode(item) for item in page['Items'])
        if 'LastEvaluatedKey' not in page:
            return result
        args['ExclusiveStartKey'] = page['LastEvaluatedKey']


def put(table, item):
    return {'Put': {'TableName': table, 'Item': encode(item),
                    'ConditionExpression': 'attribute_not_exists(PK)'}}


def check(table, key, condition, values=None, names=None):
    result = {'TableName': table, 'Key': encode(key), 'ConditionExpression': condition}
    if values:
        result['ExpressionAttributeValues'] = encode(values)
    if names:
        result['ExpressionAttributeNames'] = names
    return {'ConditionCheck': result}


def validate_transaction(actions):
    if not 1 <= len(actions) <= 100:
        raise ValueError('Una transacción admite 1–100 acciones')
    seen = set()
    for action in actions:
        op = next(iter(action.values()))
        item = decode(op.get('Item', op.get('Key')))
        key = (op['TableName'], item['PK'], item['SK'])
        if key in seen:
            raise ValueError('Dos acciones sobre el mismo ítem')
        seen.add(key)
    # Conservative JSON serialization bound, not an exact billing-size calculator.
    if len(json.dumps(actions, ensure_ascii=False).encode()) > 4 * 1024 * 1024:
        raise ValueError('Transacción demasiado grande')


def commit(client, actions):
    validate_transaction(actions)
    client.transact_write_items(TransactItems=actions)
