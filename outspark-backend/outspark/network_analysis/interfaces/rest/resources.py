from typing import Literal

from pydantic import Field

from outspark.shared.interfaces.http.documentation import ResponseResource


class SourceFileResponse(ResponseResource):
    filename: str
    sha256: str
    bytes: int


class DatasetResponse(ResponseResource):
    dataset_id: str
    schema_version: int
    status: str = Field(examples=["READY"])
    source: str
    counts: dict[str, int]
    files: dict[str, SourceFileResponse]
    full_dataset: bool
    interpretation: str


class NodeResponse(ResponseResource):
    node_id: int = Field(examples=[1])
    in_friendship_graph: bool
    degree: int
    friendship_rows: int
    wall_received: int
    wall_sent: int
    neighbor_chunks: int
    simulation_user_id: str = Field(examples=["fb-1"])


class NodesResponse(ResponseResource):
    items: list[NodeResponse]
    next_cursor: str | None


class NeighborResponse(ResponseResource):
    node_id: int


class NeighborsResponse(ResponseResource):
    items: list[NeighborResponse]
    next_cursor: str | None
    dataset_id: str
    node_id: int
    kind: str


class FriendshipRecordResponse(ResponseResource):
    source_line: int
    owner_id: int
    friend_id: int
    timestamp: int | None = Field(description="Unix UTC; null cuando la fuente contiene \\N.")


class FriendshipRecordsResponse(ResponseResource):
    items: list[FriendshipRecordResponse]
    next_cursor: str | None
    dataset_id: str
    node_id: int
    kind: str


class WallEventResponse(ResponseResource):
    event_id: str = Field(
        description="Referencia a la línea de la fuente; no es un ID de publicación de Outspark."
    )
    source_line: int
    wall_owner_id: int
    author_id: int
    timestamp: int = Field(description="Fecha Unix UTC de la fuente.")
    content_available: Literal[False] = Field(description="False: la fuente no contiene texto.")


class WallEventsResponse(ResponseResource):
    items: list[WallEventResponse]
    next_cursor: str | None
    dataset_id: str
    node_id: int
    kind: str


class ReachRound(ResponseResource):
    hops: int
    new_nodes: int
    total_without_seed: int


class ReachResponse(ResponseResource):
    seed: int
    max_hops: int
    rounds: list[ReachRound]
    visited_nodes: int
    complete: bool
    dataset_id: str
    relation: str
    storage: dict[str, int | float]
    interpretation: str


class StructuralDegreeResponse(ResponseResource):
    node_id: int
    group_id: int
    degree: int


class StructuralSummaryResponse(ResponseResource):
    dataset_id: str
    source_sha256: str
    run_id: str
    status: Literal["READY"]
    method: str
    full_graph: bool
    complete: bool
    nodes: int
    edges: int
    groups: int
    visited_nodes: int
    elapsed_seconds: str
    degree_ranking: list[StructuralDegreeResponse]
    interpretation: str


class StructuralGroupResponse(StructuralDegreeResponse):
    dataset_id: str
    run_id: str
    group_size: int
    full_graph: bool
    method: str
