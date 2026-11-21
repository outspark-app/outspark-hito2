from fastapi import Request

from ...application.commandservices.publications import PublicationCommands
from ...application.queryservices.diffusion import PublicationDiffusion
from ...application.queryservices.publications import PublicationQueries


def queries(request: Request) -> PublicationQueries:
    return request.app.state.publishing_queries


def commands(request: Request) -> PublicationCommands:
    return request.app.state.publishing_commands


def diffusion(request: Request) -> PublicationDiffusion:
    return request.app.state.publication_diffusion
