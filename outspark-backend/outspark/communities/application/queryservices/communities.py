from outspark.shared.application.contracts import ConsistencyGuard
from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import identifier

from ...domain.repositories.communities import CommunitiesRepository


class CommunityQueries:
    def __init__(self, repository: CommunitiesRepository):
        self.repository = repository

    def active(self, community):
        item = self.repository.community(identifier(community))
        if not item:
            raise UseCaseError(404, "community_missing", "Comunidad inexistente.")
        if item["status"] != "ACTIVE":
            raise UseCaseError(410, "community_removed", "Comunidad retirada.")
        return item

    def validate_topics(self, topics):
        for topic in topics:
            if not self.repository.topic_exists(identifier(topic)):
                raise UseCaseError(400, "topic_missing", "Tema inexistente.")
        return tuple(ConsistencyGuard("communities", "topic", topic) for topic in topics)

    def publishing_permit(self, actor, community, topics):
        self.active(community)
        if not self.repository.member(actor, community):
            raise UseCaseError(403, "membership_required", "Únete a la comunidad para publicar.")
        return (
            ConsistencyGuard("communities", "active", community),
            self.member_guard(actor, community),
            *self.validate_topics(topics),
        )

    def member_guard(self, actor, community):
        return ConsistencyGuard("communities", "membership", actor, community)

    def catalog(self, kind, limit=20, cursor=None):
        return self.repository.catalog(kind, limit, cursor)

    def memberships(self, actor, limit=20, cursor=None):
        return self.repository.memberships(actor, limit, cursor)

    def member_window(self, actor, budget):
        return self.repository.member_window(actor, budget)

    def catalog_window(self, budget):
        return self.repository.catalog_window(budget)
