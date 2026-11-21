from fastapi import APIRouter, Depends

from outspark.shared.interfaces.http.dependencies import actor
from outspark.shared.interfaces.http.documentation import responses

from ...application.commandservices.preferences import PreferenceCommands
from ...application.queryservices.profiles import ProfileQueries
from .dependencies import commands, queries
from .resources import MeResponse, PreferencesResource, PreferencesResponse

router = APIRouter(prefix="/api/me", tags=["Profiles"])


@router.get(
    "",
    status_code=200,
    operation_id="readMyProfile",
    summary="Consultar mi perfil y preferencias",
    description="Devuelve la cuenta autenticada y la versión de sus preferencias. La identidad procede de Authorize; no se envía en el JSON.",
    responses=responses(
        MeResponse,
        "Consultar mi perfil y preferencias",
        status=200,
        errors=(400, 401, 403, 413, 500, 503),
        replay=False,
    ),
)
def me(service: ProfileQueries = Depends(queries), user: str = Depends(actor)):
    return service.me(user)


@router.put(
    "/preferences",
    status_code=200,
    operation_id="updateMyPreferences",
    summary="Actualizar mis preferencias",
    description="Usa la versión actual de GET /api/me. El servidor aumenta la versión en uno. Una actualización concurrente con versión anterior devuelve 409; [] elimina los temas preferidos.",
    responses=responses(
        PreferencesResponse,
        "Actualizar mis preferencias",
        status=200,
        errors=(400, 401, 403, 409, 413, 500, 503),
        replay=False,
    ),
)
def preferences(
    body: PreferencesResource,
    service: PreferenceCommands = Depends(commands),
    user: str = Depends(actor),
):
    return service.change(user, body.topic_ids, body.version)
