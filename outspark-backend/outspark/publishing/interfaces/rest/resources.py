from typing import Annotated

from pydantic import Field

from outspark.shared.interfaces.http.documentation import ResponseResource
from outspark.shared.interfaces.http.resources import Resource

NodeId = Annotated[int, Field(ge=0, lt=10**12)]


class DiffusionResource(Resource):
    origin: NodeId | None = None
    max_hops: int = Field(default=2, ge=1, le=3)
    slots: int = Field(default=3, ge=1, le=10)
    custom_contacts: list[NodeId] | None = Field(default=None, max_length=10)


class DiffusionContact(ResponseResource):
    node_id: int
    degree: int


class DiffusionRound(ResponseResource):
    hop: int
    new_nodes: int
    total: int


class DiffusionPlan(ResponseResource):
    contacts: list[int]
    reachable: int
    rounds: list[DiffusionRound]


class DiffusionResponse(ResponseResource):
    publication_id: str
    dataset_id: str
    origin: int
    max_hops: int
    slots: int
    contacts: list[DiffusionContact]
    degree: DiffusionPlan
    greedy: DiffusionPlan
    custom: DiffusionPlan | None


class PublishResource(Resource):
    community_id: str = Field(
        description="Comunidad activa de la que la cuenta es miembro.", examples=["diseno"]
    )
    body: str = Field(
        description="Texto de 1 a 1000 caracteres después de quitar espacios de los extremos.",
        examples=["Una idea conecta comunidades."],
    )
    topic_ids: list[str] = Field(
        description="De uno a tres temas distintos y existentes en GET /api/topics.",
        examples=[["diseno"]],
        json_schema_extra={"minItems": 1, "maxItems": 3, "uniqueItems": True},
    )


class RepostResource(Resource):
    parent_event_id: str = Field(
        description="Copia el event_id de una respuesta real de publicación o republicación. El ejemplo ilustra el formato; no es un evento existente.",
        examples=["publicacion-demo/evento-raiz"],
    )


class CommentResource(Resource):
    body: str = Field(
        description="Texto de 1 a 1000 caracteres después de quitar espacios de los extremos.",
        examples=["Me gustaría explorar esta idea."],
    )


class PublicationResponse(ResponseResource):
    publication_id: str
    author_id: str
    community_id: str
    body: str | None = Field(
        default=None,
        description="Solo aparece cuando el original está activo. Se omite al retirarlo.",
    )
    topic_ids: list[str]
    visibility: str = Field(examples=["public"])
    status: str = Field(examples=["ACTIVE", "REMOVED"])
    root_event_id: str = Field(
        description="Evento raíz; puede usarse como padre de una republicación."
    )
    created_at: str = Field(json_schema_extra={"format": "date-time"})
    message: str | None = Field(
        default=None, description="Mensaje que sustituye al texto del original retirado."
    )
    entity_type: str | None = None


class RepostResponse(ResponseResource):
    publication_id: str = Field(description="Original al que pertenece el evento nuevo.")
    event_id: str = Field(
        description="Referencia opaca del evento nuevo; puede ser padre del siguiente repost."
    )
    replayed: bool = Field(
        description="true si la clave de idempotencia recuperó un resultado anterior."
    )


class CreatedPublicationResponse(RepostResponse):
    publication: PublicationResponse


class CommentResponse(ResponseResource):
    comment_id: str
    publication_id: str
    author_id: str
    body: str
    created_at: str = Field(json_schema_extra={"format": "date-time"})
    replayed: bool | None = None
    status: str | None = None
    entity_type: str | None = None


class CommentsResponse(ResponseResource):
    items: list[CommentResponse]
    next_cursor: str | None = Field(
        description="Cursor opaco de esta lista de comentarios; null al terminar."
    )


class PublicationsResponse(ResponseResource):
    unavailable_count: int = Field(
        default=0,
        ge=0,
        description="Originales referenciados por eventos de esta página cuyos datos no están disponibles; se informa sin bloquear páginas posteriores.",
    )
    items: list[PublicationResponse]
    next_cursor: str | None = Field(
        description="Cursor opaco del historial de esta cuenta; null al terminar. Una página sin originales puede tener continuación si evaluó republicaciones."
    )
