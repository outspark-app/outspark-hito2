class PublishingFacade:
    """Proyecciones públicas. Eventos sin claves físicas; procedencia completa o error."""

    def __init__(self, queries, repository):
        self._queries, self._repository = queries, repository

    def original(self, publication_id):
        return self._queries.read(publication_id)

    def originals(self, ids, budget):
        posts, pending = self._repository.originals(ids, budget)
        return {
            pid: self._queries.render(post)
            for pid, post in posts.items()
            if post["visibility"] == "public"
        }, pending

    def activity(self, actor, limit, budget):
        return self._repository.activity(actor, limit, budget)

    def community_roots(self, community, limit, budget):
        return self._repository.community_roots(community, limit, budget)

    def provenance(self, publication_id, source_ids, budget=None):
        return self._queries.paths(publication_id, source_ids, budget)

    def active_guard(self, publication_id):
        return self._queries.guard(publication_id)
