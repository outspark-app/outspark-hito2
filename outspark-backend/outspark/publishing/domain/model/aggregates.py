"""Agregados y reglas independientes de persistencia y transporte."""

from dataclasses import dataclass, replace

from outspark.publishing.domain.model.value_objects import EventReference
from outspark.shared.domain.value_objects import RuleViolation, content, identifier, topic_ids


@dataclass(frozen=True)
class PublicationDraft:
    author_id: str
    community_id: str
    body: str
    topics: tuple[str, ...]

    @classmethod
    def create(cls, author, community, body, topics):
        return cls(
            identifier(author), identifier(community), content(body), tuple(topic_ids(topics, 1))
        )


@dataclass(frozen=True)
class Publication:
    publication_id: str
    author_id: str
    status: str
    visibility: str
    root_event_id: str

    @classmethod
    def from_record(cls, record):
        return cls(
            *(
                record[k]
                for k in ("publication_id", "author_id", "status", "visibility", "root_event_id")
            )
        )

    def require_public(self):
        if self.visibility != "public":
            raise RuleViolation("private_publication", "Contenido no público.")

    def require_active(self):
        self.require_public()
        if self.status != "ACTIVE":
            raise RuleViolation("publication_removed", "Publicación retirada.")

    def retire(self, actor):
        if self.author_id != actor:
            raise RuleViolation("author_required", "Solo el autor puede retirar el original.")
        return replace(self, status="REMOVED")

    def validate_repost(self, actor, parent, already_participated):
        self.require_active()
        ref = EventReference.parse(parent["event_id"])
        if (
            parent["publication_id"] != self.publication_id
            or ref.publication_id != self.publication_id
        ):
            raise RuleViolation("cross_publication", "El padre pertenece a otro original.")
        if self.author_id == actor or already_participated:
            raise RuleViolation("already_participated", "Esta cuenta ya participa en el original.")
