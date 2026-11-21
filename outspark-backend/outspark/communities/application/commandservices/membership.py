from ...domain.model.aggregates import Membership
from ...domain.repositories.communities import CommunitiesRepository
from ..outboundservices.actors import Actors


class MembershipCommands:
    def __init__(self, repository: CommunitiesRepository, queries, actors: Actors, clock):
        self.repository, self.queries, self.actors, self.clock = repository, queries, actors, clock

    def change(self, actor, community, active):
        active_actor = self.actors.active_guard(actor)
        self.queries.active(community)
        states = self.repository.membership_states(actor, community)
        membership = Membership.change(actor, community, active, states)
        if (states and states[0] == membership.status) or (not states and not active):
            return {"community_id": community, "status": membership.status}
        from outspark.shared.application.contracts import ConsistencyGuard

        guards = (active_actor, ConsistencyGuard("communities", "active", community))
        self.repository.save_membership(membership, states, self.clock(), guards)
        return {"community_id": community, "status": membership.status}
