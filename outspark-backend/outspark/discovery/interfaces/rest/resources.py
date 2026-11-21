from typing import Literal

from pydantic import Field

from outspark.shared.interfaces.http.documentation import ResponseResource
from outspark.shared.interfaces.http.resources import Resource


class FeedResource(Resource):
    strategy: str = Field(
        default="chronological",
        description="chronological ordena por actividad; diverse usa selección voraz con diversidad de comunidades.",
        examples=["chronological", "diverse"],
        json_schema_extra={"enum": ["chronological", "diverse"]},
    )


# The consumer owns its published projections; no import of Publishing REST internals.
class FeedPublicationResponse(ResponseResource):
    publication_id: str
    author_id: str
    community_id: str
    body: str | None = Field(
        default=None,
        description="Se omite si el original fue retirado después de crear el snapshot.",
    )
    topic_ids: list[str]
    visibility: str
    status: str
    root_event_id: str
    created_at: str = Field(json_schema_extra={"format": "date-time"})
    message: str | None = None
    entity_type: str | None = None


class ArrivalReasonResponse(ResponseResource):
    type: Literal["own", "contact", "community", "discovery"]
    text: str = Field(description="Explicación registrada al generar el snapshot.")
    contact_id: str | None = None
    community_id: str | None = None


class FeedSourceResponse(ResponseResource):
    event_id: str
    reasons: list[ArrivalReasonResponse]


class FeedCardResponse(ResponseResource):
    publication_id: str
    position: int = Field(description="Posición desde cero en el snapshot.")
    sources: list[FeedSourceResponse]
    relevance: str = Field(description="Puntuación decimal expresada como cadena.")
    selection_reason: str
    publication: FeedPublicationResponse


class ObservedPreferences(ResponseResource):
    topic_ids: list[str]
    version: int


class FeedMetrics(ResponseResource):
    cards: int
    communities: int
    objective: str
    mean_relevance: str


class RetrievalResponse(ResponseResource):
    query_pages: int
    query_budget: int
    truncated: bool = Field(
        description="true si se acotó la recuperación de candidatos. Nunca declara completo un árbol parcial."
    )
    windows: list[dict] = Field(
        description="Ventanas y alcance observados; metadatos de diagnóstico."
    )
    query_batch_read_units: str
    unprocessed_originals: int


class SelectionResponse(ResponseResource):
    candidate_hash: str = Field(
        description="Hash del mismo conjunto materializado que usan ambas estrategias en la comparación."
    )
    candidate_events: int
    candidate_originals: int
    reference_at: str = Field(json_schema_extra={"format": "date-time"})
    preferences: ObservedPreferences
    parameters: dict = Field(
        description="Pesos, recencia, cupo por autor y máximo de tarjetas utilizados."
    )
    retrieval: RetrievalResponse
    metrics: FeedMetrics


class FeedSnapshotResponse(ResponseResource):
    snapshot_id: str = Field(description="Identificador para consultar este feed y sus rutas.")
    viewer_id: str
    strategy: Literal["chronological", "diverse"]
    algorithm_version: str
    generated_at: str = Field(json_schema_extra={"format": "date-time"})
    cards: list[FeedCardResponse]
    source_count: int
    limits: dict[str, int]
    selection: SelectionResponse
    entity_type: str | None = None


class ComparedFeedsResponse(ResponseResource):
    chronological: FeedSnapshotResponse
    diverse: FeedSnapshotResponse


class ComparisonResponse(ResponseResource):
    feeds: ComparedFeedsResponse
    candidate_hash: str


class ProvenanceEventResponse(ResponseResource):
    publication_id: str
    actor_id: str
    parent_event_id: str | None = Field(description="null únicamente en la raíz del original.")
    event_id: str
    created_at: str = Field(json_schema_extra={"format": "date-time"})
    entity_type: str | None = None


class ArrivalRouteResponse(ResponseResource):
    source: FeedSourceResponse
    events: list[ProvenanceEventResponse] = Field(
        description="Ruta ordenada desde el autor original hasta el evento fuente."
    )


class DfsVisitResponse(ResponseResource):
    event_id: str
    depth: int


class ProvenanceTreeResponse(ResponseResource):
    dfs: list[DfsVisitResponse]
    event_count: int


class ProvenanceResponse(ResponseResource):
    snapshot_id: str
    viewer_id: str
    publication: FeedPublicationResponse
    routes: list[ArrivalRouteResponse]
    tree: ProvenanceTreeResponse
