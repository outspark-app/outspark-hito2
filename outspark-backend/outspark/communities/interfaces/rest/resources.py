from pydantic import Field

from outspark.shared.interfaces.http.documentation import ResponseResource


class CommunityResponse(ResponseResource):
    community_id: str = Field(examples=["diseno"])
    name: str = Field(examples=["Diseño"])
    status: str = Field(examples=["ACTIVE"])
    entity_type: str | None = None


class TopicResponse(ResponseResource):
    topic_id: str = Field(examples=["tecnologia"])
    name: str = Field(examples=["Tecnología"])
    entity_type: str | None = None


class MembershipResponse(ResponseResource):
    community_id: str = Field(examples=["diseno"])
    status: str = Field(examples=["ACTIVE", "REMOVED"])
    created_at: str | None = Field(default=None, json_schema_extra={"format": "date-time"})
    entity_type: str | None = None


class CommunitiesResponse(ResponseResource):
    items: list[CommunityResponse]
    next_cursor: str | None = Field(description="Cursor opaco de esta lista; null al terminar.")


class TopicsResponse(ResponseResource):
    items: list[TopicResponse]
    next_cursor: str | None


class MembershipsResponse(ResponseResource):
    items: list[MembershipResponse]
    next_cursor: str | None
