from dataclasses import dataclass

from outspark.shared.domain.value_objects import RuleViolation, identifier, topic_ids


@dataclass(frozen=True)
class Preferences:
    user_id: str
    topics: tuple[str, ...]
    version: int

    @classmethod
    def change(cls, actor, topics, version):
        if type(version) is not int or version < 0:
            raise RuleViolation("invalid_version", "Versión entera no negativa requerida.")
        return cls(identifier(actor), tuple(topic_ids(topics)), version + 1)
