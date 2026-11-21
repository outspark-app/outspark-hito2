from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import identifier

from ...domain.model.dataset import node_id
from ...domain.repositories.analyses import StructuralResultsRepository
from ...domain.repositories.datasets import DatasetsRepository
from ...domain.services.structural import METHOD


class StructuralQueries:
    def __init__(self, results: StructuralResultsRepository, datasets: DatasetsRepository):
        self.results, self.datasets = results, datasets

    def summary(self, dataset_id):
        dataset_id = identifier(dataset_id)
        manifest = self.datasets.manifest(dataset_id)
        if not manifest or manifest["status"] != "READY":
            raise UseCaseError(404, "dataset_missing", "Dataset verificado no disponible.")
        result = self.results.latest(dataset_id)
        if not result:
            raise UseCaseError(404, "analysis_missing", "Aún no hay análisis estructural guardado.")
        if result.get("method") != METHOD:
            raise UseCaseError(
                409,
                "analysis_method_stale",
                "El análisis usa un método anterior; vuelve a calcular las componentes por BFS.",
            )
        if result["source_sha256"] != manifest["files"]["links"]["sha256"]:
            raise UseCaseError(
                409, "analysis_stale", "El análisis corresponde a otra versión del dataset."
            )
        return result

    def group(self, dataset_id, uid):
        summary = self.summary(dataset_id)
        group = self.results.node_group(dataset_id, summary["run_id"], node_id(uid))
        if group is None:
            raise UseCaseError(
                404, "group_outside_scope", "El nodo no pertenece al grafo de amistades analizado."
            )
        return {
            **group,
            "dataset_id": dataset_id,
            "run_id": summary["run_id"],
            "full_graph": summary["full_graph"],
            "method": summary["method"],
        }
