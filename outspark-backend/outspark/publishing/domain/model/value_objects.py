from dataclasses import dataclass

from outspark.shared.domain.value_objects import RuleViolation, identifier


@dataclass(frozen=True)
class EventReference:
    publication_id: str
    event_id: str

    def __post_init__(self):
        identifier(self.publication_id)
        identifier(self.event_id)

    @classmethod
    def parse(cls, value):
        if not isinstance(value, str) or value.count("/") != 1:
            raise RuleViolation("invalid_event", "Referencia de evento inválida")
        return cls(*value.split("/"))
