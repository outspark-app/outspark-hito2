from outspark.communities.interfaces.acl.facade import CommunitiesFacade
from outspark.connections.interfaces.acl.facade import ConnectionsFacade
from outspark.profiles.interfaces.acl.facade import ProfilesFacade
from outspark.publishing.interfaces.acl.facade import PublishingFacade


class ProfileGateway:
    def __init__(self, facade: ProfilesFacade):
        self.facade = facade

    def actor(self, actor):
        snapshot = self.facade.actor(actor)
        return {
            "user_id": snapshot.user_id,
            "topic_ids": list(snapshot.topics),
            "version": snapshot.preferences_version,
            "active_guard": snapshot.active_guard,
        }


class ConnectionGateway:
    def __init__(self, facade: ConnectionsFacade):
        self.facade = facade

    def contacts(self, actor, budget):
        return self.facade.contacts(actor, budget)

    def active_guard(self, actor, other):
        return self.facade.active_guard(actor, other)


class CommunityGateway:
    def __init__(self, facade: CommunitiesFacade):
        self.facade = facade

    def memberships(self, actor, budget):
        return self.facade.memberships(actor, budget)

    def catalog(self, budget):
        return self.facade.catalog(budget)

    def membership_guard(self, actor, community):
        return self.facade.membership_guard(actor, community)


class PublishingGateway:
    def __init__(self, facade: PublishingFacade):
        self.facade = facade

    def original(self, pid):
        return self.facade.original(pid)

    def originals(self, ids, budget):
        return self.facade.originals(ids, budget)

    def activity(self, actor, limit, budget):
        return self.facade.activity(actor, limit, budget)

    def community_roots(self, community, limit, budget):
        return self.facade.community_roots(community, limit, budget)

    def provenance(self, pid, sources, budget=None):
        return self.facade.provenance(pid, sources, budget)

    def active_guard(self, pid):
        return self.facade.active_guard(pid)
