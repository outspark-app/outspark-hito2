from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from outspark.shared.interfaces.http.dependencies import actor, page_limit
from outspark.shared.interfaces.http.documentation import responses

from ...application.commandservices.membership import MembershipCommands
from ...application.queryservices.communities import CommunityQueries
from .dependencies import commands, queries
from .resources import CommunitiesResponse, MembershipResponse, MembershipsResponse, TopicsResponse

router = APIRouter(prefix="/api", tags=["Communities"])


@router.get(
    "/communities",
    status_code=200,
    operation_id="listCommunities",
    summary="Listar comunidades activas",
    description="Catálogo paginado de comunidades donde se publican originales. Las comunidades de demo son diseno, tecnologia y sostenibilidad.",
    responses=responses(
        CommunitiesResponse,
        "Listar comunidades activas",
        status=200,
        errors=(400, 401, 403, 413, 500, 503),
        replay=False,
    ),
)
def catalog(
    service: CommunityQueries = Depends(queries),
    user: str = Depends(actor),
    limit: int = Depends(page_limit),
    cursor: str | None = Query(
        default=None,
        description="Copia next_cursor de la página anterior de esta misma lista; omítelo en la primera página.",
    ),
):
    return service.catalog("communities", limit, cursor)


@router.get(
    "/topics",
    status_code=200,
    operation_id="listTopics",
    summary="Listar temas del catálogo",
    description="Obtén topic_id válidos antes de publicar o actualizar preferencias. Las publicaciones admiten de uno a tres temas distintos.",
    responses=responses(
        TopicsResponse,
        "Listar temas del catálogo",
        status=200,
        errors=(400, 401, 403, 413, 500, 503),
        replay=False,
    ),
)
def topics(
    service: CommunityQueries = Depends(queries),
    user: str = Depends(actor),
    limit: int = Depends(page_limit),
    cursor: str | None = Query(
        default=None,
        description="Copia next_cursor de la página anterior de esta misma lista; omítelo en la primera página.",
    ),
):
    return service.catalog("topics", limit, cursor)


@router.get(
    "/me/communities",
    status_code=200,
    operation_id="listMyMemberships",
    summary="Listar mis comunidades",
    description="Devuelve las membresías activas de la cuenta autenticada. La lista se pagina con limit y next_cursor.",
    responses=responses(
        MembershipsResponse,
        "Listar mis comunidades",
        status=200,
        errors=(400, 401, 403, 413, 500, 503),
        replay=False,
    ),
)
def memberships(
    service: CommunityQueries = Depends(queries),
    user: str = Depends(actor),
    limit: int = Depends(page_limit),
    cursor: str | None = Query(
        default=None,
        description="Copia next_cursor de la página anterior de esta misma lista; omítelo en la primera página.",
    ),
):
    return service.memberships(user, limit, cursor)


@router.put(
    "/me/communities/{community}",
    status_code=200,
    operation_id="joinCommunity",
    summary="Unirme a una comunidad",
    description="Activa la membresía y permite publicar en esta comunidad. Repetir la operación mantiene ACTIVE. La comunidad y la cuenta deben estar activas.",
    responses=responses(
        MembershipResponse,
        "Unirme a una comunidad",
        status=200,
        errors=(400, 401, 403, 404, 409, 410, 413, 500, 503),
        replay=False,
    ),
)
def join(
    community: Annotated[
        str, Path(description="Identificador de la comunidad activa.", examples=["diseno"])
    ],
    service: MembershipCommands = Depends(commands),
    user: str = Depends(actor),
):
    return service.change(user, community, True)


@router.delete(
    "/me/communities/{community}",
    status_code=200,
    operation_id="leaveCommunity",
    summary="Salir de una comunidad",
    description="Retira la membresía. No permite crear nuevos originales allí. Los snapshots ya guardados conservan sus razones de llegada; un reintento idempotente de una publicación anterior puede recuperar el resultado confirmado.",
    responses=responses(
        MembershipResponse,
        "Salir de una comunidad",
        status=200,
        errors=(400, 401, 403, 404, 409, 410, 413, 500, 503),
        replay=False,
    ),
)
def leave(
    community: Annotated[
        str, Path(description="Identificador de la comunidad activa.", examples=["diseno"])
    ],
    service: MembershipCommands = Depends(commands),
    user: str = Depends(actor),
):
    return service.change(user, community, False)
