from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import identifier

from ...domain.model.aggregates import FeedSnapshot
from ...domain.repositories.snapshots import SnapshotsRepository
from ..outboundservices.network import Publishing


class SnapshotQueries:
    def __init__(self, repository: SnapshotsRepository, publishing: Publishing):
        self.repository, self.publishing = repository, publishing

    def checked(self, actor, snapshot_id):
        snapshot = self.repository.snapshot(identifier(snapshot_id))
        if not snapshot:
            raise UseCaseError(404, "snapshot_missing", "Snapshot inexistente.")
        FeedSnapshot(snapshot_id, snapshot["viewer_id"]).require_owner(actor)
        return snapshot

    def read(self, actor, snapshot_id):
        snapshot = self.checked(actor, snapshot_id)
        return {
            **snapshot,
            "cards": [
                {**card, "publication": self.publishing.original(card["publication_id"])}
                for card in snapshot["cards"]
            ],
        }

    def provenance(self, actor, snapshot_id, publication_id):
        snapshot = self.checked(actor, snapshot_id)
        card = next((c for c in snapshot["cards"] if c["publication_id"] == publication_id), None)
        if not card:
            raise UseCaseError(404, "card_missing", "La tarjeta no pertenece a este snapshot.")
        evidence = self.publishing.provenance(
            publication_id, [s["event_id"] for s in card["sources"]]
        )
        return {
            "snapshot_id": snapshot_id,
            "viewer_id": actor,
            "publication": evidence["publication"],
            "routes": [
                {"source": source, "events": path}
                for source, path in zip(card["sources"], evidence["paths"])
            ],
            "tree": evidence["tree"],
        }
