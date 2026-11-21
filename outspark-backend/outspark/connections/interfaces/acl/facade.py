class ConnectionsFacade:
    def __init__(self, queries):
        self._queries = queries

    def contacts(self, actor, budget) -> list[str]:
        return self._queries.window(actor, budget)

    def active_guard(self, actor, other):
        return self._queries.guard(actor, other)
