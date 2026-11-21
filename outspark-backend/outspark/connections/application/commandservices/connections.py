from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import identifier

from ...domain.model.aggregates import Friendship
from ...domain.repositories.connections import ConnectionsRepository
from ..outboundservices.actors import Actors
from ..outboundservices.historical_network import HistoricalNetwork


class ConnectionCommands:
    def __init__(
        self,
        repository: ConnectionsRepository,
        actors: Actors,
        historical: HistoricalNetwork | None = None,
    ):
        self.repository, self.actors, self.historical = repository, actors, historical

    def remove(self, actor, other):
        identifier(actor)
        identifier(other)
        active = self.actors.active_guard(actor)
        if self.historical and self.historical.supports(actor):
            self.historical.active_guard(actor, other)
            raise UseCaseError(
                409,
                "historical_contact_read_only",
                "La amistad pertenece al dataset histórico inmutable.",
            )
        states = self.repository.friendship_states(actor, other)
        if not states:
            raise UseCaseError(404, "contact_missing", "Contacto inexistente.")
        friendship = Friendship.remove(actor, other, states)
        if states[0] == "ACTIVE":
            self.repository.remove(friendship, actor, (active,))
        return {"contact_id": other, "status": friendship.status}
