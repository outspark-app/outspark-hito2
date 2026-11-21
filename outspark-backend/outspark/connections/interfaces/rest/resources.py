from pydantic import Field

from outspark.shared.interfaces.http.documentation import ResponseResource


class ContactResponse(ResponseResource):
    contact_id: str = Field(description="La otra cuenta de la conexión.", examples=["bruno"])
    status: str = Field(examples=["ACTIVE"])
    entity_type: str | None = None
    historical: bool | None = Field(
        default=None, description="True en amistades históricas inmutables."
    )
    source: str | None = Field(default=None, description="Identificador del dataset de origen.")


class ContactsResponse(ResponseResource):
    items: list[ContactResponse]
    next_cursor: str | None = Field(
        description="Cursor opaco para continuar esta misma consulta; null al terminar."
    )


class RemovedContactResponse(ResponseResource):
    contact_id: str
    status: str = Field(examples=["REMOVED"])
