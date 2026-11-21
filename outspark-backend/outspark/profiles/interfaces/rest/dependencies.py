from fastapi import Request

from ...application.commandservices.preferences import PreferenceCommands
from ...application.queryservices.profiles import ProfileQueries


def queries(request: Request) -> ProfileQueries:
    return request.app.state.profiles_queries


def commands(request: Request) -> PreferenceCommands:
    return request.app.state.profiles_commands
