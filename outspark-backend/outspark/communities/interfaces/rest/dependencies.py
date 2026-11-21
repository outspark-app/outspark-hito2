from fastapi import Request

from ...application.commandservices.membership import MembershipCommands
from ...application.queryservices.communities import CommunityQueries


def queries(request: Request) -> CommunityQueries:
    return request.app.state.communities_queries


def commands(request: Request) -> MembershipCommands:
    return request.app.state.communities_commands
