"""Presupuesto de lectura compartido por caso de uso y adaptador."""

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal


class QueryBudget:
    def __init__(self, maximum=60):
        self.maximum, self.pages, self.units, self.truncated = maximum, 0, 0, False
        self.windows = []

    def take(self):
        if self.pages >= self.maximum:
            self.truncated = True
            return False
        self.pages += 1
        return True


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fields(data, required):
    from .errors import UseCaseError

    if not isinstance(data, dict) or set(data) != set(required):
        raise UseCaseError(400, "invalid_fields", "Campos faltantes o no permitidos.")


def digest(payload):
    def number(value):
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral() else str(value)
        raise TypeError(type(value).__name__)

    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=number
        ).encode()
    ).hexdigest()
