from typing import Annotated

from fastapi import APIRouter, Depends, Path

from outspark.shared.interfaces.http.dependencies import actor
from outspark.shared.interfaces.http.documentation import responses

from ...application.commandservices.feeds import FeedCommands
from ...application.queryservices.snapshots import SnapshotQueries
from .dependencies import commands, queries
from .resources import ComparisonResponse, FeedResource, FeedSnapshotResponse, ProvenanceResponse

router = APIRouter(prefix="/api/feed", tags=["Discovery"])


@router.post(
    "/snapshots",
    status_code=201,
    operation_id="createFeedSnapshot",
    summary="Generar mi feed y guardar un snapshot",
    description="Crea un snapshot propio con hasta diez originales distintos y dos por autor. Cada tarjeta conserva eventos fuente y razones de llegada. chronological usa actividad reciente; diverse aplica selección voraz por relevancia y diversidad. La recuperación de candidatos está acotada y se registra en selection.retrieval.",
    responses=responses(
        FeedSnapshotResponse,
        "Generar mi feed y guardar un snapshot",
        status=201,
        errors=(400, 401, 403, 404, 409, 413, 422, 500, 503),
        replay=False,
    ),
)
def generate(
    body: FeedResource,
    service: FeedCommands = Depends(commands),
    user: str = Depends(actor),
):
    return service.generate(user, body.strategy)


@router.post(
    "/comparisons",
    status_code=201,
    operation_id="compareFeedSnapshots",
    summary="Comparar feed cronológico y diverso",
    description="Crea dos snapshots propios usando los mismos candidatos materializados, preferencias e instante. Ambos conservan el mismo candidate_hash. No requiere cuerpo. Comparar métricas no demuestra optimalidad general ni satisfacción de usuarios.",
    responses=responses(
        ComparisonResponse,
        "Comparar feed cronológico y diverso",
        status=201,
        errors=(400, 401, 403, 404, 409, 413, 422, 500, 503),
        replay=False,
    ),
)
def compare(service: FeedCommands = Depends(commands), user: str = Depends(actor)):
    return service.generate(user, compare=True)


@router.get(
    "/{snapshot_id}",
    status_code=200,
    operation_id="readFeedSnapshot",
    summary="Consultar mi snapshot",
    description="Solo su receptor puede consultarlo. El orden y las razones se conservan; el texto visible refleja si el original fue retirado después de generar el feed.",
    responses=responses(
        FeedSnapshotResponse,
        "Consultar mi snapshot",
        status=200,
        errors=(400, 401, 403, 404, 413, 500, 503),
        replay=False,
    ),
)
def snapshot(
    snapshot_id: Annotated[
        str,
        Path(
            description="Copia snapshot_id de un feed generado por esta cuenta.",
            examples=["snapshot-demo"],
        ),
    ],
    service: SnapshotQueries = Depends(queries),
    user: str = Depends(actor),
):
    return service.read(user, snapshot_id)


@router.get(
    "/{snapshot_id}/cards/{publication_id}/provenance",
    status_code=200,
    operation_id="readCardProvenance",
    summary="Ver cómo llegó esta tarjeta a mí",
    description="Reconstruye las rutas hasta cada evento fuente registrado y la DFS del árbol completo del original. La tarjeta debe pertenecer a este snapshot y la cuenta debe ser su receptor. Admite hasta 1000 eventos; si no puede recuperar todo responde 422. El receptor no se cuenta como republicador si no realizó esa acción.",
    responses=responses(
        ProvenanceResponse,
        "Ver cómo llegó esta tarjeta a mí",
        status=200,
        errors=(400, 401, 403, 404, 413, 422, 500, 503),
        replay=False,
    ),
)
def provenance(
    snapshot_id: Annotated[
        str,
        Path(
            description="Copia snapshot_id de un feed generado por esta cuenta.",
            examples=["snapshot-demo"],
        ),
    ],
    publication_id: Annotated[
        str,
        Path(
            description="Copia publication_id de una respuesta real.", examples=["publicacion-demo"]
        ),
    ],
    service: SnapshotQueries = Depends(queries),
    user: str = Depends(actor),
):
    return service.provenance(user, snapshot_id, publication_id)
