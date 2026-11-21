from outspark.shared.application.contracts import ConsistencyGuard
from outspark.shared.application.errors import UseCaseError

from ...domain.model.dataset import DEFAULT_DATASET, simulation_node, simulation_user


class NetworkFacade:
    """Topología histórica inmutable; no publica repositorios ni claves DynamoDB."""

    def __init__(self, queries, dataset_id=DEFAULT_DATASET):
        self.queries, self.dataset_id = queries, dataset_id

    def supports(self, actor):
        return simulation_node(actor) is not None

    def diffusion(self, actor, *, origin, max_hops, slots, custom_contacts):
        if origin is None:
            origin = simulation_node(actor)
            origin = 1 if origin is None else origin
        return self.queries.diffusion(self.dataset_id, origin, max_hops, slots, custom_contacts)

    def contacts(self, actor, limit=20, cursor=None):
        node = simulation_node(actor)
        page = self.queries.records(self.dataset_id, node, "neighbors", limit, cursor)
        return {
            "items": [
                {
                    "contact_id": simulation_user(item["node_id"]),
                    "status": "ACTIVE",
                    "source": self.dataset_id,
                    "historical": True,
                }
                for item in page["items"]
            ],
            "next_cursor": page["next_cursor"],
        }

    def window(self, actor, budget):
        node = simulation_node(actor)
        self.queries.node(self.dataset_id, node)
        reads = {"calls": 0, "maximum": budget.maximum - budget.pages}
        adjacency = self.queries.repository.neighbors_many(self.dataset_id, [node], reads)
        budget.pages += reads["calls"]
        budget.units += reads.get("units", 0)
        contacts = sorted(adjacency[node])[:40]
        if len(adjacency[node]) > 40:
            budget.truncated = True
        budget.windows.append(
            {
                "source": self.dataset_id,
                "kind": "historical_contacts",
                "count": len(contacts),
                "total_contacts": len(adjacency[node]),
                "batch_requests": reads["calls"],
            }
        )
        return [simulation_user(uid) for uid in contacts]

    def active_guard(self, actor, other):
        node, peer = simulation_node(actor), simulation_node(other)
        if node is None or peer is None:
            raise UseCaseError(404, "contact_missing", "Contacto histórico inexistente.")
        self.queries.node(self.dataset_id, node)
        adjacency = self.queries.repository.neighbors_many(
            self.dataset_id, [node], {"calls": 0, "maximum": 8}
        )
        if peer not in adjacency[node]:
            raise UseCaseError(404, "contact_missing", "Contacto histórico inexistente.")
        return ConsistencyGuard("network_analysis", "ready_dataset", self.dataset_id)
