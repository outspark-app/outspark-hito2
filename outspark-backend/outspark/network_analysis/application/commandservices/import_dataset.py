from outspark.shared.domain.value_objects import identifier

from ...domain.repositories.imports import DatasetSource, ImportRepository
from ..outboundservices.profiles import SimulationProfiles


class ImportDataset:
    """Activa el histórico únicamente después de verificar datos y provisionar simulaciones."""

    def __init__(self, repository: ImportRepository, profiles: SimulationProfiles):
        self.repository, self.profiles = repository, profiles

    def execute(self, source: DatasetSource, *, resume=False):
        metadata = source.metadata
        identifier(metadata["dataset_id"])
        state = self.repository.begin(metadata, resume)
        if state["status"] == "READY":
            verification = self.repository.verify(
                metadata["dataset_id"], state["inventory"], state["files"]
            )
            return {**state, "verification": verification, "replayed": True}
        verification = None
        if resume:
            inventory = self.repository.preview(source)
            try:
                verification = self.repository.verify(
                    metadata["dataset_id"], inventory, metadata["files"]
                )
            except ValueError:
                inventory = self.repository.write(source)
        else:
            inventory = self.repository.write(source)
        if verification is None:
            verification = self.repository.verify(
                metadata["dataset_id"], inventory, metadata["files"]
            )
        counts, actual = metadata["counts"], verification["counts"]
        expected = {
            "nodes": counts["nodes"],
            "neighbors": counts["unique_friendships"] * 2,
            "friendship_rows": counts["friendship_rows"],
            "wall_received": counts["wall_events"],
            "wall_sent": counts["wall_events"],
        }
        if any(actual[key] != value for key, value in expected.items()):
            raise ValueError("Las proyecciones no contienen todos los registros del dataset.")
        profiles = self.profiles.provision(source.node_ids(), metadata["dataset_id"])
        return self.repository.finish(metadata, inventory, verification, profiles)
