from fastapi import Request

from ...application.commandservices.connections import ConnectionCommands
from ...application.queryservices.connections import ConnectionQueries


def queries(request: Request) -> ConnectionQueries:
    return request.app.state.connections_queries


def commands(request: Request) -> ConnectionCommands:
    return request.app.state.connections_commands
