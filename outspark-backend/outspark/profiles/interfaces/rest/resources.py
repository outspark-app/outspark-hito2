from pydantic import Field

from outspark.shared.interfaces.http.documentation import ResponseResource
from outspark.shared.interfaces.http.resources import Resource


class PreferencesResource(Resource):
    topic_ids: list[str] = Field(
        description="Hasta tres temas distintos del catálogo; [] elimina las preferencias.",
        examples=[["diseno", "tecnologia"]],
        json_schema_extra={"maxItems": 3, "uniqueItems": True},
    )
    version: int = Field(
        description="Versión actual obtenida de GET /api/me. Usar 0 si aún no existen preferencias.",
        examples=[1],
        json_schema_extra={"minimum": 0},
    )


class PreferencesResponse(ResponseResource):
    topic_ids: list[str]
    version: int = Field(
        description="Versión actual; aumenta en uno después de actualizar.", examples=[2]
    )
    entity_type: str | None = None


class ProfileResponse(ResponseResource):
    uid: str = Field(description="Identificador de la cuenta autenticada.", examples=["ana"])
    name: str = Field(examples=["Ana"])
    status: str = Field(examples=["ACTIVE"])
    is_demo: bool | None = Field(default=None, description="Indica si es una cuenta ficticia.")
    created_at: str | None = Field(default=None, json_schema_extra={"format": "date-time"})
    entity_type: str | None = None
    profile_origin: str | None = Field(
        default=None,
        description="dataset_simulation en las cuentas locales provisionadas desde el histórico.",
    )
    source_dataset_id: str | None = None
    dataset_node_id: int | None = None


class MeResponse(ResponseResource):
    profile: ProfileResponse
    preferences: PreferencesResponse
