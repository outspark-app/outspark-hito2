class CommunitiesFacade:
    def __init__(self, queries):
        self._queries = queries

    def validate_topics(self, topics):
        return self._queries.validate_topics(topics)

    def publishing_permit(self, actor, community, topics):
        return self._queries.publishing_permit(actor, community, topics)

    def memberships(self, actor, budget):
        return self._queries.member_window(actor, budget)

    def catalog(self, budget):
        return self._queries.catalog_window(budget)

    def membership_guard(self, actor, community):
        return self._queries.member_guard(actor, community)
