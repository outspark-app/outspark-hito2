from outspark.shared.application.contracts import ConsistencyGuard

from ...domain.repositories.connections import ConnectionsRepository
from ..outboundservices.historical_network import HistoricalNetwork


class ConnectionQueries:
    def __init__(
        self, repository: ConnectionsRepository, historical: HistoricalNetwork | None = None
    ):
        self.repository, self.historical = repository, historical

    def contacts(self, actor, limit=20, cursor=None):
        if self.historical and self.historical.supports(actor):
            return self.historical.contacts(actor, limit, cursor)
        return self.repository.contacts(actor, limit, cursor)

    def window(self, actor, budget):
        if self.historical and self.historical.supports(actor):
            return self.historical.window(actor, budget)
        return self.repository.contact_window(actor, budget)

    def guard(self, actor, other):
        if self.historical and self.historical.supports(actor):
            return self.historical.active_guard(actor, other)
        return ConsistencyGuard("connections", "active_contact", actor, other)
