from dataclasses import dataclass

from outspark.shared.application.contracts import ConsistencyGuard


@dataclass(frozen=True)
class ActorSnapshot:
    user_id: str
    topics: tuple[str, ...]
    preferences_version: int
    active_guard: ConsistencyGuard


class ProfilesFacade:
    """Lenguaje publicado: no expone repositorios ni agregados del proveedor."""

    def __init__(self, queries, imported=None):
        self._queries, self._imported = queries, imported

    def provision_imported(self, users, source):
        if self._imported is None:
            raise ValueError("Provisionamiento de simulaciones no configurado")
        return self._imported.provision(users, source)

    def actor(self, user_id) -> ActorSnapshot:
        me = self._queries.me(user_id)
        return ActorSnapshot(
            user_id,
            tuple(me["preferences"]["topic_ids"]),
            int(me["preferences"]["version"]),
            self._queries.active_guard(user_id),
        )
