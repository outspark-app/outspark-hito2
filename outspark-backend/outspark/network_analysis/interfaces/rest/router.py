from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request

from outspark.shared.interfaces.http.dependencies import actor, page_limit
from outspark.shared.interfaces.http.documentation import responses

from ...application.queryservices.datasets import DatasetQueries
from .resources import (
    DatasetResponse,
    FriendshipRecordsResponse,
    NeighborsResponse,
    NodeResponse,
    NodesResponse,
    ReachResponse,
    StructuralGroupResponse,
    StructuralSummaryResponse,
    WallEventsResponse,
)

router = APIRouter(
    prefix="/api/network/datasets", tags=["Network Analysis"], dependencies=[Depends(actor)]
)
DatasetId = Annotated[
    str, Path(description="Dataset importado y verificado.", examples=["facebook-wosn2009"])
]
NodeId = Annotated[
    int, Path(ge=0, description="Identificador anónimo original del dataset.", examples=[1])
]
Cursor = Annotated[str | None, Query(description="Cursor opaco de esta misma lista.")]
ERRORS = (400, 401, 403, 404, 409, 413, 500, 503)


def queries(request: Request) -> DatasetQueries:
    return request.app.state.network_queries


@router.get(
    "/{dataset_id}",
    operation_id="readDataset",
    summary="Consultar la importación completa",
    description="Fuente, hashes, recuentos y verificación de todos los datos. Solo se expone cuando el manifiesto está READY.",
    responses=responses(DatasetResponse, "Dataset completo verificado.", errors=ERRORS),
)
def manifest(dataset_id: DatasetId, service=Depends(queries)):
    return service.manifest(dataset_id)


@router.get(
    "/{dataset_id}/nodes",
    operation_id="listDatasetNodes",
    summary="Listar los usuarios del dataset",
    description="Incluye usuarios del grafo y los presentes solo en el muro. Publica sus cuentas locales fb-<id> para simulaciones.",
    responses=responses(NodesResponse, "Nodos paginados.", errors=ERRORS),
)
def nodes(
    dataset_id: DatasetId,
    limit=Depends(page_limit),
    cursor: Cursor = None,
    service=Depends(queries),
):
    return service.nodes(dataset_id, limit, cursor)


@router.get(
    "/{dataset_id}/nodes/{node_id}",
    operation_id="readDatasetNode",
    summary="Consultar un usuario histórico",
    description="Grado y cantidades de registros del nodo anónimo. La cuenta de simulación no representa una sesión real de Facebook.",
    responses=responses(NodeResponse, "Nodo y métricas.", errors=ERRORS),
)
def node(dataset_id: DatasetId, node_id: NodeId, service=Depends(queries)):
    return service.node(dataset_id, node_id)


@router.get(
    "/{dataset_id}/nodes/{node_id}/neighbors",
    operation_id="listDatasetNeighbors",
    summary="Consultar las amistades normalizadas",
    description="Vecinos únicos del grafo no dirigido. Las filas originales y sus fechas se consultan por separado.",
    responses=responses(NeighborsResponse, "Amistades paginadas.", errors=ERRORS),
)
def neighbors(
    dataset_id: DatasetId,
    node_id: NodeId,
    limit=Depends(page_limit),
    cursor: Cursor = None,
    service=Depends(queries),
):
    return service.records(dataset_id, node_id, "neighbors", limit, cursor)


@router.get(
    "/{dataset_id}/nodes/{node_id}/friendship-records",
    operation_id="listFriendshipRecords",
    summary="Consultar las filas originales de amistad",
    description="Preserva cada fila dirigida, duplicados, fecha nullable y número de línea. Primera columna: owner_id; segunda: friend_id.",
    responses=responses(
        FriendshipRecordsResponse, "Registros originales paginados.", errors=ERRORS
    ),
)
def friendships(
    dataset_id: DatasetId,
    node_id: NodeId,
    limit=Depends(page_limit),
    cursor: Cursor = None,
    service=Depends(queries),
):
    return service.records(dataset_id, node_id, "links", limit, cursor)


@router.get(
    "/{dataset_id}/nodes/{node_id}/wall-events",
    operation_id="listHistoricalWallEvents",
    summary="Consultar la actividad histórica de muro",
    description="Autor (segunda columna) → dueño del muro (primera columna), con fecha real y sin contenido. Orden descendente por fecha y línea. No son publicaciones ni republicaciones de Outspark.",
    responses=responses(WallEventsResponse, "Eventos históricos paginados.", errors=ERRORS),
)
def wall(
    dataset_id: DatasetId,
    node_id: NodeId,
    direction: Literal["received", "sent"] = Query(default="received"),
    limit=Depends(page_limit),
    cursor: Cursor = None,
    service=Depends(queries),
):
    return service.records(dataset_id, node_id, "wall_" + direction, limit, cursor)


@router.get(
    "/{dataset_id}/nodes/{node_id}/reach",
    operation_id="readHistoricalReach",
    summary="Calcular el alcance por BFS",
    description="BFS por niveles sobre las amistades completas desde DynamoDB. De uno a tres saltos, hasta 100000 visitados y 128 peticiones BatchGet. Si se supera el presupuesto devuelve 422; no publica resultados truncados. Alcance topológico, sin afirmar difusión histórica de contenido.",
    responses=responses(
        ReachResponse, "Alcance completo hasta los saltos solicitados.", errors=(*ERRORS, 422)
    ),
)
def reach(
    dataset_id: DatasetId,
    node_id: NodeId,
    max_hops: int = Query(default=3, ge=1, le=3),
    service=Depends(queries),
):
    return service.reach(dataset_id, node_id, max_hops)


@router.get(
    "/{dataset_id}/analysis",
    operation_id="readStructuralAnalysis",
    summary="Consultar componentes y grados precalculados",
    description="Componentes conexas por BFS y grado de cada nodo. Publica versión, hash de entrada y alcance. No se recalcula al consultar y no representa influencia observada.",
    responses=responses(StructuralSummaryResponse, "Análisis estructural guardado.", errors=ERRORS),
)
def analysis(dataset_id: DatasetId, request: Request):
    return request.app.state.structural_queries.summary(dataset_id)


@router.get(
    "/{dataset_id}/analysis/nodes/{node_id}",
    operation_id="readStructuralNodeGroup",
    summary="Consultar la componente conexa de un nodo",
    description="Componente canónica, tamaño y grado del nodo. Nodos exclusivos del muro quedan fuera del grafo de amistades.",
    responses=responses(
        StructuralGroupResponse, "Pertenencia estructural guardada.", errors=ERRORS
    ),
)
def analysis_group(dataset_id: DatasetId, node_id: NodeId, request: Request):
    return request.app.state.structural_queries.group(dataset_id, node_id)
