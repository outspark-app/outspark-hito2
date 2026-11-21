from dataclasses import dataclass

from outspark.shared.domain.value_objects import RuleViolation, identifier


@dataclass(frozen=True)
class Friendship:
    first: str
    second: str
    status: str

    @classmethod
    def remove(cls, actor, other, states):
        identifier(actor)
        identifier(other)
        if actor == other:
            raise RuleViolation("self_contact", "Una cuenta no es su propio contacto.")
        if len(states) != 3 or len(set(states)) != 1:
            raise RuleViolation("contact_inconsistent", "Contacto inconsistente.")
        return cls(*sorted((actor, other)), "REMOVED")
