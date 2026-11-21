from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from outspark.shared.interfaces.http.dependencies import actor, page_limit
from outspark.shared.interfaces.http.documentation import responses

from ...application.commandservices.connections import ConnectionCommands
from ...application.queryservices.connections import ConnectionQueries
from .dependencies import commands, queries
from .resources import ContactsResponse, RemovedContactResponse

router = APIRouter(prefix="/api/me/contacts", tags=["Connections"])


@router.get(
    "",
    status_code=200,
    operation_id="listMyContacts",
    summary="Listar mis contactos",
    description="Consulta paginada de conexiones activas. next_cursor solo sirve para continuar la misma lista de esta cuenta.",
    responses=responses(
        ContactsResponse,
        "Listar mis contactos",
        status=200,
        errors=(400, 401, 403, 413, 500, 503),
        replay=False,
    ),
)
def contacts(
    service: ConnectionQueries = Depends(queries),
    user: str = Depends(actor),
    limit: int = Depends(page_limit),
    cursor: str | None = Query(
        default=None,
        description="Copia next_cursor de la página anterior de esta misma lista; omítelo en la primera página.",
    ),
):
    return service.contacts(user, limit, cursor)


@router.delete(
    "/{other}",
    status_code=200,
    operation_id="removeMyContact",
    summary="Retirar un contacto",
    description="Retira la conexión mutua. Los nuevos feeds ya no usan este contacto; las razones de snapshots anteriores se conservan. En la demo existen inicialmente las conexiones Diego–Bruno y Diego–Carla.",
    responses=responses(
        RemovedContactResponse,
        "Retirar un contacto",
        status=200,
        errors=(400, 401, 403, 404, 409, 413, 500, 503),
        replay=False,
    ),
)
def remove_contact(
    other: Annotated[
        str, Path(description="Identificador del contacto que deseas retirar.", examples=["bruno"])
    ],
    service: ConnectionCommands = Depends(commands),
    user: str = Depends(actor),
):
    return service.remove(user, other)
