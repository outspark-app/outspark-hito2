import logging

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import Field
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import RuleViolation

from .boundary import RequestBoundary
from .documentation import ResponseResource, responses

LOG = logging.getLogger("outspark")


class HealthResponse(ResponseResource):
    status: str = Field(examples=["ok"])
    service: str = Field(examples=["outspark"])
    version: str = Field(examples=["0.2.0"])


def http_application(local_demo, *, storage_name="DynamoDB Local"):
    engine_name = storage_name.removesuffix(" Local")
    app = FastAPI(
        title="Outspark API",
        version="0.2.0",
        summary="Publicar, republicar y explicar cómo llegó una idea a una cuenta.",
        description=(
            "Backend modular de Outspark. Esta documentación se genera desde los routers y recursos de cada bounded context.\n\n"
            + (
                "## Demo local\nPulsa **Authorize** y escribe `ana`, `bruno`, `carla`, `diego` o `elena`. "
                "Tras importar el histórico puedes usar `fb-1` u otra cuenta `fb-<id>` de simulación. "
                "Son cuentas locales sin contraseña ni claves AWS. La sesión de Swagger no se guarda al recargar.\n\n"
                if local_demo
                else "## Identidad en Lambda\nEl autorizador JWT de API Gateway valida el token de Cognito; la Lambda usa el `sub` verificado. "
                "El encabezado de demo se ignora. El despliegue de Cognito/API Gateway sigue pendiente.\n\n"
            )
            + "## Recorrido\n1. Como Ana: consulta los catálogos y publica en `diseno`.\n"
            "2. Como Bruno: republica usando el `event_id` recibido.\n"
            "3. Como Carla: republica usando el evento de Bruno.\n"
            "4. Como Diego: genera un snapshot y consulta cómo llegó esa tarjeta.\n\n"
            "Usa identificadores de respuestas reales; los valores de los ejemplos ilustran el formato. "
            "Las tres escrituras de Publishing requieren `Idempotency-Key`: mismo contenido recupera el resultado (200), "
            "contenido distinto con la misma clave devuelve 409. El JSON no admite autor ni receptor enviados por el cliente.\n\n"
            f"## Alcance de los datos\nLa importación explícita del histórico de Facebook conserva en {storage_name} "
            "todos los nodos, filas de amistad, eventos de muro y bytes originales. Consulta su estado y recuentos "
            "en **Network Analysis**; se expone solo después de verificar la carga completa. "
            "Las cuentas `fb-<id>` usan sus amistades para el feed de simulaciones. Los eventos históricos de muro "
            "tienen fechas y participantes, sin texto ni trazas observadas de republicación. "
            "Publicar y republicar en Outspark genera acciones nuevas, separadas del histórico.\n\n"
            "JSON UTF-8, cuerpos de hasta 16 KiB y listas paginadas. Las razones de un snapshot permanecen; "
            "el texto retirado deja de mostrarse. Autenticación real, AWS y conexión del frontend siguen pendientes."
        ),
        openapi_tags=[
            {"name": "Operations", "description": "Estado del proceso y documentación de la API."},
            {"name": "Profiles", "description": "Mi perfil y preferencias con control de versión."},
            {
                "name": "Connections",
                "description": "Contactos activos y retirada de conexiones mutuas.",
            },
            {
                "name": "Communities",
                "description": "Catálogos de comunidades y temas; mis membresías.",
            },
            {
                "name": "Publishing",
                "description": "Originales, republicaciones y comentarios. Identidad y fechas del servidor.",
            },
            {
                "name": "Discovery",
                "description": "Feed, comparación y explicación de las rutas guardadas.",
            },
            {
                "name": "Network Analysis",
                "description": f"Dataset histórico completo en {engine_name}: usuarios, amistades, muro y BFS. Datos históricos separados de acciones nuevas.",
            },
        ],
        swagger_ui_parameters={
            "displayRequestDuration": True,
            "filter": True,
            "docExpansion": "none",
            "persistAuthorization": False,
        },
    )
    app.state.local_demo = local_demo
    app.add_middleware(RequestBoundary, local_demo=local_demo)

    def error(status, code, message):
        return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)

    @app.exception_handler(UseCaseError)
    async def use_case(request, exc):
        return error(exc.status, exc.code, exc.message)

    @app.exception_handler(RuleViolation)
    async def rule(request, exc):
        status = {
            "snapshot_owner": 403,
            "author_required": 403,
            "private_publication": 403,
            "already_participated": 409,
            "contact_inconsistent": 409,
            "membership_inconsistent": 409,
            "publication_removed": 410,
            "reach_limit": 422,
        }.get(exc.code, 400)
        return error(status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation(request, exc):
        return error(
            400,
            "invalid_fields",
            "Campos, JSON o parámetros no válidos; consulta el contrato en /docs.",
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return error(400, "invalid_data", str(exc))

    @app.exception_handler(ClientError)
    async def client_error(request, exc):
        code = exc.response["Error"]["Code"]
        if code in ("TransactionCanceledException", "ConditionalCheckFailedException"):
            return error(409, "write_conflict", "Conflicto de estado o escritura concurrente.")
        LOG.error("storage_error request_id=%s code=%s", request.scope.get("request_id"), code)
        return error(503, "storage_unavailable", "Persistencia no disponible.")

    @app.exception_handler(BotoCoreError)
    async def storage_error(request, exc):
        return error(503, "storage_unavailable", "Persistencia no disponible.")

    @app.exception_handler(Exception)
    async def internal(request, exc):
        LOG.error(
            "internal_error request_id=%s type=%s",
            request.scope.get("request_id"),
            type(exc).__name__,
        )
        return error(500, "internal_error", "Error interno.")

    @app.get(
        "/api/health",
        tags=["Operations"],
        operation_id="readHealth",
        summary="Consultar el estado del proceso",
        description=f"Público. Confirma que la API responde; no consulta {engine_name} ni acredita su disponibilidad.",
        responses=responses(
            HealthResponse,
            "Proceso HTTP disponible.",
            errors=(413, 500),
            example={"status": "ok", "service": "outspark", "version": "0.2.0"},
        ),
    )
    def health():
        return {"status": "ok", "service": "outspark", "version": "0.2.0"}

    return app
