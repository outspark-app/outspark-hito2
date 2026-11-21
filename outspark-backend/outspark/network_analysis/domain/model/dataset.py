"""Identidad del histórico y cuentas locales para simular sobre su topología."""

from dataclasses import dataclass

from outspark.shared.domain.value_objects import RuleViolation, identifier

DEFAULT_DATASET = "facebook-wosn2009"


def node_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 10**12:
        raise RuleViolation("invalid_node", "Identificador de nodo no válido.")
    return value


def simulation_user(node):
    return f"fb-{node_id(node)}"


def simulation_node(user):
    if not isinstance(user, str) or not user.startswith("fb-"):
        return None
    suffix = user[3:]
    if not suffix.isdigit() or str(int(suffix)) != suffix:
        return None
    return node_id(int(suffix))


@dataclass(frozen=True)
class DatasetIdentity:
    dataset_id: str

    def __post_init__(self):
        identifier(self.dataset_id)
