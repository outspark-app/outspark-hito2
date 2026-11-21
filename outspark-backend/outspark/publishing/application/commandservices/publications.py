from outspark.shared.application.models import fields
from outspark.shared.domain.value_objects import content

from ...domain.model.aggregates import Publication, PublicationDraft
from ...domain.repositories.publications import PublicationsRepository
from ..outboundservices.actors import Actors
from ..outboundservices.communities import CommunityPermits


class PublicationCommands:
    def __init__(
        self,
        repository: PublicationsRepository,
        queries,
        actors: Actors,
        communities: CommunityPermits,
        clock,
    ):
        self.repository, self.queries, self.actors, self.communities, self.clock = (
            repository,
            queries,
            actors,
            communities,
            clock,
        )

    def publish(self, actor, data, key):
        fields(data, ("community_id", "body", "topic_ids"))
        draft = PublicationDraft.create(
            actor, data["community_id"], data["body"], data["topic_ids"]
        )
        active = self.actors.active_guard(actor)
        self.communities.topics(list(draft.topics))
        payload = {
            "operation": "publish",
            "community_id": draft.community_id,
            "body": draft.body,
            "topic_ids": list(draft.topics),
        }
        old = self.repository.replay(actor, key, payload)
        if old:
            return {
                **old,
                "publication": self.queries.read(old["publication_id"]),
                "replayed": True,
            }
        guards = (active, *self.communities.permit(actor, draft.community_id, list(draft.topics)))
        result = self.repository.publish(draft, key, payload, self.clock(), guards)
        return {**result, "publication": self.queries.read(result["publication_id"])}

    def repost(self, actor, data, key):
        fields(data, ("parent_event_id",))
        active = self.actors.active_guard(actor)
        payload = {"operation": "repost", "parent_event_id": data["parent_event_id"]}
        old = self.repository.replay(actor, key, payload)
        if old:
            return {**old, "replayed": True}
        parent = self.queries.event(data["parent_event_id"])
        post = self.queries.original(parent["publication_id"], active=True)
        Publication.from_record(post).validate_repost(
            actor, parent, self.repository.participated(post["publication_id"], actor)
        )
        return self.repository.repost(
            actor,
            parent,
            key,
            payload,
            self.clock(),
            (active, self.queries.guard(post["publication_id"])),
        )

    def comment(self, actor, publication_id, data, key):
        fields(data, ("body",))
        body = content(data["body"])
        active = self.actors.active_guard(actor)
        self.queries.original(publication_id, active=True)
        payload = {"operation": "comment", "publication_id": publication_id, "body": body}
        old = self.repository.replay(actor, key, payload)
        if old:
            return {**old, "replayed": True}
        return self.repository.comment(
            actor,
            publication_id,
            body,
            key,
            payload,
            self.clock(),
            (active, self.queries.guard(publication_id)),
        )

    def retire(self, actor, publication_id):
        active = self.actors.active_guard(actor)
        post = self.queries.original(publication_id)
        Publication.from_record(post).retire(actor)
        if post["status"] == "ACTIVE":
            self.repository.retire(publication_id, (active,))
        return self.queries.read(publication_id)
