from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from outspark.shared.interfaces.http.dependencies import actor, idempotency_key, page_limit
from outspark.shared.interfaces.http.documentation import responses

from ...application.commandservices.publications import PublicationCommands
from ...application.queryservices.diffusion import PublicationDiffusion
from ...application.queryservices.publications import PublicationQueries
from .dependencies import commands, diffusion, queries
from .resources import (
    CommentResource,
    CommentResponse,
    CommentsResponse,
    CreatedPublicationResponse,
    DiffusionResource,
    DiffusionResponse,
    PublicationResponse,
    PublicationsResponse,
    PublishResource,
    RepostResource,
    RepostResponse,
)

router = APIRouter(prefix="/api", tags=["Publishing"])


def created(response, result):
    response.status_code = 200 if result["replayed"] else 201
    return result


@router.post(
    "/publications",
    status_code=201,
    operation_id="createPublication",
    summary="Publicar una idea",
    description="Crea el original y su evento raíz. Requiere pertenencia activa, temas del catálogo e Idempotency-Key. El servidor fija autor, identificadores y fecha. Copia event_id para el siguiente paso de republicación.",
    responses=responses(
        CreatedPublicationResponse,
        "Publicar una idea",
        status=201,
        errors=(400, 401, 403, 404, 409, 410, 413, 500, 503),
        replay=True,
    ),
)
def publish(
    body: PublishResource,
    response: Response,
    service: PublicationCommands = Depends(commands),
    user: str = Depends(actor),
    key: str = Depends(idempotency_key),
):
    return created(response, service.publish(user, body.model_dump(), key))


@router.post(
    "/reposts",
    status_code=201,
    operation_id="createRepost",
    summary="Republicar desde un evento",
    description="Copia parent_event_id de una respuesta real; el servidor deriva el original. Cada cuenta puede participar una sola vez en ese original, incluido su autor. No exige pertenencia a la comunidad original. Requiere Idempotency-Key.",
    responses=responses(
        RepostResponse,
        "Republicar desde un evento",
        status=201,
        errors=(400, 401, 403, 404, 409, 410, 413, 500, 503),
        replay=True,
    ),
)
def repost(
    body: RepostResource,
    response: Response,
    service: PublicationCommands = Depends(commands),
    user: str = Depends(actor),
    key: str = Depends(idempotency_key),
):
    return created(response, service.repost(user, body.model_dump(), key))


@router.get(
    "/publications/{publication_id}",
    status_code=200,
    operation_id="readPublication",
    summary="Consultar un original",
    description="Devuelve un original público. Si fue retirado responde 200 con status=REMOVED y omite body; conserva su identidad y el evento raíz para explicar rutas históricas.",
    responses=responses(
        PublicationResponse,
        "Consultar un original",
        status=200,
        errors=(400, 401, 403, 404, 413, 500, 503),
        replay=False,
    ),
)
def publication(
    publication_id: Annotated[
        str,
        Path(
            description="Copia publication_id de una respuesta real.", examples=["publicacion-demo"]
        ),
    ],
    service: PublicationQueries = Depends(queries),
    user: str = Depends(actor),
):
    return service.read(publication_id)


@router.post(
    "/publications/{publication_id}/diffusion",
    operation_id="compareDiffusionPlans",
    summary="Simular difusión de mi publicación",
    description=(
        "Compara planes de contactos en la red histórica. Los resultados cuentan "
        "perfiles alcanzables por BFS y no generan actividad."
    ),
    responses=responses(
        DiffusionResponse,
        "Planes y alcance por salto",
        errors=(400, 401, 403, 404, 409, 410, 413, 422, 500, 503),
    ),
)
def publication_diffusion(
    publication_id: str,
    body: DiffusionResource,
    service: PublicationDiffusion = Depends(diffusion),
    user: str = Depends(actor),
):
    return service.preview(publication_id, user, body.model_dump())


@router.delete(
    "/publications/{publication_id}",
    status_code=200,
    operation_id="retirePublication",
    summary="Retirar mi original",
    description="Solo el autor puede retirar el original. Oculta el texto y los comentarios, impide nuevos reposts y comentarios y conserva los eventos históricos. Repetir el retiro devuelve el estado REMOVED.",
    responses=responses(
        PublicationResponse,
        "Retirar mi original",
        status=200,
        errors=(400, 401, 403, 404, 409, 413, 500, 503),
        replay=False,
    ),
)
def retire(
    publication_id: Annotated[
        str,
        Path(
            description="Copia publication_id de una respuesta real.", examples=["publicacion-demo"]
        ),
    ],
    service: PublicationCommands = Depends(commands),
    user: str = Depends(actor),
):
    return service.retire(user, publication_id)


@router.get(
    "/publications/{publication_id}/comments",
    status_code=200,
    operation_id="listPublicationComments",
    summary="Listar comentarios",
    description="Consulta paginada de comentarios activos. Usa el next_cursor de este original. Los comentarios de un original retirado quedan ocultos y responden 410.",
    responses=responses(
        CommentsResponse,
        "Listar comentarios",
        status=200,
        errors=(400, 401, 403, 404, 410, 413, 500, 503),
        replay=False,
    ),
)
def comments(
    publication_id: Annotated[
        str,
        Path(
            description="Copia publication_id de una respuesta real.", examples=["publicacion-demo"]
        ),
    ],
    service: PublicationQueries = Depends(queries),
    user: str = Depends(actor),
    limit: int = Depends(page_limit),
    cursor: str | None = Query(
        default=None,
        description="Copia next_cursor de la página anterior de esta misma lista; omítelo en la primera página.",
    ),
):
    return service.comments(publication_id, limit, cursor)


@router.post(
    "/publications/{publication_id}/comments",
    status_code=201,
    operation_id="createPublicationComment",
    summary="Comentar un original",
    description="Crea un comentario público en un original activo con Idempotency-Key. El autor y la fecha los fija el servidor. Si el original se retira, incluso reintentar un comentario anterior responde 410.",
    responses=responses(
        CommentResponse,
        "Comentar un original",
        status=201,
        errors=(400, 401, 403, 404, 409, 410, 413, 500, 503),
        replay=True,
    ),
)
def comment(
    publication_id: Annotated[
        str,
        Path(
            description="Copia publication_id de una respuesta real.", examples=["publicacion-demo"]
        ),
    ],
    body: CommentResource,
    response: Response,
    service: PublicationCommands = Depends(commands),
    user: str = Depends(actor),
    key: str = Depends(idempotency_key),
):
    return created(
        response,
        service.comment(user, publication_id, body.model_dump(), key),
    )


@router.get(
    "/me/publications",
    status_code=200,
    operation_id="listMyPublications",
    summary="Consultar mis publicaciones originales",
    description="Historial propio por fecha descendente, independiente del feed y sus diez tarjetas. La identidad se toma de la sesión. Evalúa hasta limit eventos del índice de actividad, omite republicaciones e hidrata los originales desde la tabla base; una página vacía puede tener next_cursor. Continúa hasta cursor null. Incluye retirados sin texto. Si un evento referencia un original inexistente, informa unavailable_count y permite continuar; las lecturas sin procesar devuelven 503 sin avanzar. El índice tiene consistencia eventual: una publicación nueva puede tardar en aparecer; actualiza desde el inicio para incluirla. No es un snapshot cerrado entre páginas.",
    responses=responses(PublicationsResponse, "Mis publicaciones originales", replay=False),
)
def my_publications(
    service: PublicationQueries = Depends(queries),
    user: str = Depends(actor),
    limit: int = Depends(page_limit),
    cursor: str | None = Query(
        default=None, description="Cursor recibido para el historial de esta misma cuenta."
    ),
):
    return service.own(user, limit, cursor)
