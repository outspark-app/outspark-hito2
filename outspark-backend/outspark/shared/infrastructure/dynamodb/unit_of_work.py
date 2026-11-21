from botocore.exceptions import BotoCoreError, ClientError

from outspark.shared.application.errors import UseCaseError

from . import operations as db


class UnitOfWork:
    """Cada proveedor traduce sus propias garantías; el consumidor no conoce claves."""

    def __init__(self, storage):
        self.storage, self.resolvers = storage, {}

    def register(self, owner, resolver):
        self.resolvers[owner] = resolver

    def actions(self, guards):
        checks = {}
        for guard in guards:
            action = self.resolvers[guard.owner](guard)
            operation = action["ConditionCheck"]
            key = (
                operation["TableName"],
                tuple(sorted((k, v["S"]) for k, v in operation["Key"].items())),
            )
            if key in checks and checks[key] != action:
                raise ValueError("Garantías contradictorias sobre el mismo registro")
            checks[key] = action
        return list(checks.values())

    def commit(self, writes, guards=()):
        try:
            db.commit(self.storage.client, [*self.actions(guards), *writes])
        except ClientError as error:
            if error.response["Error"]["Code"] in (
                "TransactionCanceledException",
                "ConditionalCheckFailedException",
            ):
                raise UseCaseError(
                    409, "write_conflict", "Conflicto de estado o escritura concurrente."
                ) from error
            raise UseCaseError(503, "storage_unavailable", "Persistencia no disponible.") from error
        except BotoCoreError as error:
            raise UseCaseError(503, "storage_unavailable", "Persistencia no disponible.") from error


def state_update(table, pk, sk, desired, previous):
    return {
        "Update": {
            "TableName": table,
            "Key": db.encode({"PK": pk, "SK": sk}),
            "UpdateExpression": "SET #s = :new",
            "ConditionExpression": "#s = :old",
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": db.encode({":new": desired, ":old": previous}),
        }
    }
