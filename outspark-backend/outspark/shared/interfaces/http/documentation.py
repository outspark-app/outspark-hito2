"""Contrato OpenAPI compartido de transporte; no contiene modelos de negocio."""

from pydantic import BaseModel, ConfigDict, Field


class ResponseResource(BaseModel):
    model_config = ConfigDict(extra="allow")


class ErrorDetail(ResponseResource):
    code: str = Field(
        description="Código estable para el cliente; depende de la operación y causa."
    )
    message: str | None = Field(
        default=None,
        description="Explicación del error, cuando está disponible.",
    )


class ErrorResponse(ResponseResource):
    error: ErrorDetail


ERROR_DESCRIPTIONS = {
    400: "Campos, JSON, identificadores, cursor, límite o clave de idempotencia no válidos.",
    401: "Identidad requerida: cuenta de demo en local o JWT validado por API Gateway.",
    403: "Cuenta inactiva, recurso de otra cuenta o permiso insuficiente.",
    404: "El recurso solicitado no existe o la tarjeta no pertenece al snapshot.",
    409: "Conflicto de versión, estado, participación o clave de idempotencia.",
    410: "Comunidad o publicación retirada; la operación ya no está permitida.",
    413: "El cuerpo supera el máximo HTTP de 16 KiB.",
    422: "No se puede recuperar la procedencia completa o el snapshot excede su límite.",
    500: "Error interno.",
    503: "Persistencia no disponible.",
}
HEADERS = {
    "x-request-id": {
        "description": "Identificador de la petición cuando está disponible.",
        "schema": {"type": "string"},
    }
}
DEFAULT_ERRORS = (400, 401, 403, 413, 500, 503)


def responses(model, description, *, status=200, errors=DEFAULT_ERRORS, replay=False, example=None):
    success = {"model": model, "description": description, "headers": HEADERS}
    if example is not None:
        success["content"] = {"application/json": {"example": example}}
    result = {
        code: {"model": ErrorResponse, "description": ERROR_DESCRIPTIONS[code], "headers": HEADERS}
        for code in errors
    }
    result[status] = success
    if replay:
        result[200] = {
            "model": model,
            "description": "Reintento idempotente: devuelve el resultado confirmado y replayed=true.",
            "headers": HEADERS,
        }
    return result


def configure_openapi(app):
    """Alinea errores de validación y autenticación con el modo de ejecución real."""
    from fastapi.openapi.utils import get_openapi

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=[{"url": "/", "description": "La misma API que sirve esta documentación."}],
        )
        schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        if app.state.local_demo:
            scheme = "DemoUser"
        else:
            schemes.pop("DemoUser", None)
            firebase = getattr(app.state, "firebase", False)
            scheme = "FirebaseJWT" if firebase else "GatewayJWT"
            schemes[scheme] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "ID token emitido por Firebase Authentication."
                    if firebase
                    else "JWT para el autorizador de API Gateway/Cognito. La Lambda usa el sub verificado. Despliegue AWS pendiente."
                ),
            }
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                if method not in ("get", "post", "put", "delete", "patch", "options", "head"):
                    continue
                if path != "/api/health":
                    operation["security"] = [{scheme: []}]
                else:
                    operation["security"] = []
                # FastAPI adds HTTPValidationError 422 by default, but the API maps it to 400.
                response = operation["responses"].get("422", {})
                ref = (
                    response.get("content", {})
                    .get("application/json", {})
                    .get("schema", {})
                    .get("$ref", "")
                )
                if ref.endswith("/HTTPValidationError"):
                    operation["responses"].pop("422")
                for parameter in operation.get("parameters", []):
                    if parameter["in"] == "header" and parameter["name"] == "Idempotency-Key":
                        parameter.update(
                            required=True,
                            example="swagger-operacion-1",
                            schema={"type": "string", "minLength": 1, "maxLength": 128},
                        )
        schemas = schema["components"].get("schemas", {})
        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)
        app.openapi_schema = schema
        return schema

    app.openapi = openapi
