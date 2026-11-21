from dataclasses import dataclass

from outspark.shared.domain.value_objects import RuleViolation, identifier


@dataclass(frozen=True)
class Membership:
    user_id: str
    community_id: str
    status: str

    @classmethod
    def change(cls, actor, community, active, states):
        if states and (len(states) != 2 or len(set(states)) != 1):
            raise RuleViolation("membership_inconsistent", "Pertenencia inconsistente.")
        return cls(identifier(actor), identifier(community), "ACTIVE" if active else "REMOVED")
