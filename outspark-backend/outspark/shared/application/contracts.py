from dataclasses import dataclass


@dataclass(frozen=True)
class ConsistencyGuard:
    owner: str
    kind: str
    subject: str
    related: str | None = None
