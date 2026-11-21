from fastapi import Header, Query, Request, Security
from fastapi.security import APIKeyHeader

from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import identifier

demo_identity = APIKeyHeader(
    name="X-Demo-User",
    scheme_name="DemoUser",
    auto_error=False,
    description="Solo demo local. Usa ana, bruno, carla, diego o elena; tras importar el histórico, también `fb-<id>` (por ejemplo `fb-1`). No es una clave AWS ni un token real.",
)


def actor(request: Request, demo_user: str | None = Security(demo_identity)):
    if request.app.state.local_demo:
        subject = demo_user
    else:
        event = request.scope.get("aws.event", {})
        subject = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("jwt", {})
            .get("claims", {})
            .get("sub")
        )
    if not isinstance(subject, str) or not subject:
        raise UseCaseError(401, "authentication_required", "Sesión requerida.")
    identifier(subject)
    request.app.state.actor_policy(subject)
    return subject


def page_limit(
    limit: int = Query(
        default=20, ge=1, le=50, description="Tamaño de página: de 1 a 50 registros evaluados."
    ),
):
    return limit


def idempotency_key(
    value: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Obligatorio. Clave de 1 a 128 caracteres, única por operación de esta cuenta. Mismo contenido recupera el resultado; contenido distinto devuelve 409.",
    ),
):
    if not value or not 1 <= len(value) <= 128:
        raise UseCaseError(
            400, "idempotency_required", "Se requiere Idempotency-Key de 1 a 128 caracteres."
        )
    return value
