from outspark.network_analysis.interfaces.acl.facade import NetworkFacade


class HistoricalNetworkGateway:
    def __init__(self, facade: NetworkFacade):
        self.facade = facade

    def supports(self, actor):
        return self.facade.supports(actor)

    def contacts(self, actor, limit, cursor):
        return self.facade.contacts(actor, limit, cursor)

    def window(self, actor, budget):
        return self.facade.window(actor, budget)

    def active_guard(self, actor, other):
        return self.facade.active_guard(actor, other)
