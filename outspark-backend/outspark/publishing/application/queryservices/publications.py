from outspark.publishing.domain.model.value_objects import EventReference
from outspark.shared.application.contracts import ConsistencyGuard
from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import identifier

from ...domain.model.aggregates import Publication
from ...domain.repositories.publications import PublicationsRepository
from ...domain.services.provenance import routes
from ...domain.services.traversal import tree_dfs


class PublicationQueries:
    def __init__(self, repository: PublicationsRepository):
        self.repository = repository

    def original(self, publication_id, active=False):
        post = self.repository.original(identifier(publication_id))
        if not post:
            raise UseCaseError(404, "publication_missing", "Publicación inexistente.")
        publication = Publication.from_record(post)
        publication.require_active() if active else publication.require_public()
        return post

    @staticmethod
    def render(post):
        result = dict(post)
        if post["status"] != "ACTIVE":
            result.pop("body", None)
            result["message"] = "Publicación retirada"
        return result

    def read(self, publication_id):
        return self.render(self.original(publication_id))

    def event(self, reference):
        EventReference.parse(reference)
        parent = self.repository.event(reference)
        if not parent:
            raise UseCaseError(404, "event_missing", "Evento padre inexistente.")
        return parent

    def own(self, actor, limit=20, cursor=None):
        page = self.repository.own_originals(identifier(actor), limit, cursor)
        return {**page, "items": [self.render(post) for post in page["items"]]}

    def comments(self, publication_id, limit=20, cursor=None):
        self.original(publication_id, active=True)
        return self.repository.comments(publication_id, limit, cursor)

    def paths(self, publication_id, sources, budget=None):
        post = self.original(publication_id)
        events = self.repository.events(publication_id, budget)
        return {
            "publication": self.render(post),
            "paths": routes(events, sources, post["root_event_id"]),
            "tree": {"dfs": tree_dfs(events, post["root_event_id"]), "event_count": len(events)},
        }

    def guard(self, publication_id):
        return ConsistencyGuard("publishing", "active_public", publication_id)
