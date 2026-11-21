from fastapi import Request

from ...application.commandservices.feeds import FeedCommands
from ...application.queryservices.snapshots import SnapshotQueries


def queries(request: Request) -> SnapshotQueries:
    return request.app.state.discovery_queries


def commands(request: Request) -> FeedCommands:
    return request.app.state.discovery_commands
