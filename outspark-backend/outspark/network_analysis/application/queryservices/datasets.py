from functools import lru_cache

from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import identifier

from ...domain.model.dataset import node_id, simulation_user
from ...domain.repositories.datasets import DatasetsRepository
from ...domain.services.diffusion import compare_plans, contact_coverage
from ...domain.services.reach import breadth_first_reach


class DatasetQueries:
    def __init__(self, repository: DatasetsRepository):
        self.repository = repository

    def manifest(self, dataset_id):
        item = self.repository.manifest(identifier(dataset_id))
        if not item:
            raise UseCaseError(404, "dataset_missing", "Dataset no importado.")
        if item["status"] != "READY":
            raise UseCaseError(409, "dataset_not_ready", "La importación aún no está verificada.")
        return item

    def node(self, dataset_id, uid):
        self.manifest(dataset_id)
        item = self.repository.node(dataset_id, node_id(uid))
        if not item:
            raise UseCaseError(404, "node_missing", "Nodo inexistente.")
        return {**item, "simulation_user_id": simulation_user(uid)}

    def nodes(self, dataset_id, limit=20, cursor=None):
        self.manifest(dataset_id)
        page = self.repository.nodes(dataset_id, limit, cursor)
        page["items"] = [
            {**item, "simulation_user_id": simulation_user(int(item["node_id"]))}
            for item in page["items"]
        ]
        return page

    def records(self, dataset_id, uid, kind, limit=20, cursor=None):
        self.node(dataset_id, uid)
        if kind not in ("neighbors", "links", "wall_received", "wall_sent"):
            raise UseCaseError(400, "invalid_records", "Tipo de registro no válido.")
        return self.repository.records(dataset_id, uid, kind, limit, cursor)

    def reach(self, dataset_id, uid, max_hops=3):
        self.node(dataset_id, uid)
        budget = {"calls": 0, "maximum": 128}
        result = breadth_first_reach(
            uid,
            max_hops,
            lambda frontier: self.repository.neighbors_many(dataset_id, frontier, budget),
        )
        return {
            **result,
            "dataset_id": dataset_id,
            "relation": "undirected_friendship",
            "storage": budget,
            "interpretation": "Alcance de la red; no demuestra difusión de un contenido.",
        }

    def diffusion(self, dataset_id, origin, max_hops, slots, custom_contacts):
        manifest = self.manifest(dataset_id)
        node_id(origin)
        # The verified friendship graph is immutable. Scope cached plans to its hash.
        source = manifest["files"]["links"]["sha256"]
        coverage = self._diffusion_contacts(dataset_id, source, origin, max_hops)
        return {
            "origin": origin,
            "max_hops": max_hops,
            "slots": slots,
            "dataset_id": dataset_id,
            **compare_plans(coverage, max_hops, slots, custom_contacts),
        }

    @lru_cache(maxsize=2)
    def _diffusion_contacts(self, dataset_id, source, origin, max_hops):
        if not self.repository.node(dataset_id, origin):
            raise UseCaseError(404, "node_missing", "El perfil histórico no existe.")
        budget = {"calls": 0, "maximum": 1600}
        try:
            return contact_coverage(
                origin,
                max_hops,
                lambda nodes: self.repository.neighbors_many(dataset_id, nodes, budget),
            )
        except UseCaseError as error:
            if error.code != "analysis_limit":
                raise
            raise UseCaseError(
                422,
                "analysis_limit",
                "Este perfil supera el límite de lectura para esos saltos. Prueba con menos saltos.",
            ) from error
