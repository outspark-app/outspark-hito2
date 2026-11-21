"""Único lugar que conoce los contextos concretos y conecta sus contratos públicos."""

from dataclasses import dataclass
from typing import Callable

from outspark.communities.application.commandservices.membership import MembershipCommands
from outspark.communities.application.queryservices.communities import CommunityQueries
from outspark.communities.infrastructure.acl.actors import ProfileActors as CommunityActors
from outspark.communities.infrastructure.persistence.dynamodb.communities import (
    DynamoCommunitiesRepository,
)
from outspark.communities.interfaces.acl.facade import CommunitiesFacade
from outspark.communities.interfaces.rest.router import router as communities_router
from outspark.connections.application.commandservices.connections import ConnectionCommands
from outspark.connections.application.queryservices.connections import ConnectionQueries
from outspark.connections.infrastructure.acl.actors import ProfileActors as ConnectionActors
from outspark.connections.infrastructure.acl.historical_network import HistoricalNetworkGateway
from outspark.connections.infrastructure.persistence.dynamodb.connections import (
    DynamoConnectionsRepository,
)
from outspark.connections.interfaces.acl.facade import ConnectionsFacade
from outspark.connections.interfaces.rest.router import router as connections_router
from outspark.discovery.application.commandservices.feeds import FeedCommands
from outspark.discovery.application.queryservices.snapshots import SnapshotQueries
from outspark.discovery.domain.services.selection import (
    ChronologicalStrategy,
    DiverseGreedyStrategy,
)
from outspark.discovery.infrastructure.acl.network import (
    CommunityGateway,
    ConnectionGateway,
    ProfileGateway,
    PublishingGateway,
)
from outspark.discovery.infrastructure.persistence.dynamodb.snapshots import (
    DynamoSnapshotsRepository,
)
from outspark.discovery.interfaces.rest.router import router as discovery_router
from outspark.network_analysis.application.commandservices.import_dataset import ImportDataset
from outspark.network_analysis.application.queryservices.datasets import DatasetQueries
from outspark.network_analysis.application.queryservices.structural import StructuralQueries
from outspark.network_analysis.infrastructure.acl.profiles import ProfileProvisioning
from outspark.network_analysis.infrastructure.importing.importer import DynamoDatasetImporter
from outspark.network_analysis.infrastructure.persistence.dynamodb.analyses import (
    DynamoStructuralResults,
)
from outspark.network_analysis.infrastructure.persistence.dynamodb.datasets import (
    DynamoDatasetsRepository,
)
from outspark.network_analysis.interfaces.acl.facade import NetworkFacade
from outspark.network_analysis.interfaces.rest.router import router as network_router
from outspark.persistence import PostgresPersistence
from outspark.profiles.application.commandservices.imported_profiles import ImportedProfiles
from outspark.profiles.application.commandservices.preferences import PreferenceCommands
from outspark.profiles.application.queryservices.profiles import ProfileQueries
from outspark.profiles.infrastructure.acl.topics import CommunityTopics
from outspark.profiles.infrastructure.persistence.dynamodb.profiles import DynamoProfilesRepository
from outspark.profiles.interfaces.acl.facade import ActorSnapshot, ProfilesFacade
from outspark.profiles.interfaces.rest.router import router as profiles_router
from outspark.publishing.application.commandservices.publications import PublicationCommands
from outspark.publishing.application.queryservices.diffusion import PublicationDiffusion
from outspark.publishing.application.queryservices.publications import PublicationQueries
from outspark.publishing.infrastructure.acl.actors import ProfileActors as PublishingActors
from outspark.publishing.infrastructure.acl.communities import CommunityPermits
from outspark.publishing.infrastructure.acl.diffusion import PublicationNetwork
from outspark.publishing.infrastructure.persistence.dynamodb.publications import (
    DynamoPublicationsRepository,
)
from outspark.publishing.interfaces.acl.facade import PublishingFacade
from outspark.publishing.interfaces.rest.router import router as publishing_router
from outspark.shared.application.models import now
from outspark.shared.infrastructure.dynamodb.unit_of_work import UnitOfWork
from outspark.shared.interfaces.http.application import http_application


@dataclass(frozen=True)
class Services:
    profiles_queries: ProfileQueries
    profiles_commands: PreferenceCommands
    connections_queries: ConnectionQueries
    connections_commands: ConnectionCommands
    communities_queries: CommunityQueries
    communities_commands: MembershipCommands
    publishing_queries: PublicationQueries
    publishing_commands: PublicationCommands
    publication_diffusion: PublicationDiffusion
    discovery_queries: SnapshotQueries
    discovery_commands: FeedCommands
    actor_policy: Callable[[str], ActorSnapshot]
    network_queries: DatasetQueries
    structural_queries: StructuralQueries


def compose(storage, clock=now):
    transactions = UnitOfWork(storage)
    profiles = DynamoProfilesRepository(storage["profiles"], transactions)
    connections = DynamoConnectionsRepository(storage["connections"], transactions)
    communities = DynamoCommunitiesRepository(storage["communities"], transactions)
    publishing = DynamoPublicationsRepository(storage["publishing"], transactions)
    snapshots = DynamoSnapshotsRepository(storage["discovery"], transactions)
    datasets = DynamoDatasetsRepository(storage["network_analysis"])
    network_queries = DatasetQueries(datasets)
    network_facade = NetworkFacade(network_queries)
    historical = HistoricalNetworkGateway(network_facade)
    for owner, repository in [
        ("profiles", profiles),
        ("connections", connections),
        ("communities", communities),
        ("publishing", publishing),
        ("network_analysis", datasets),
    ]:
        transactions.register(owner, repository.guard)
    profile_queries, community_queries = ProfileQueries(profiles), CommunityQueries(communities)
    connection_queries, publication_queries = (
        ConnectionQueries(connections, historical),
        PublicationQueries(publishing),
    )
    profiles_facade, communities_facade = (
        ProfilesFacade(profile_queries),
        CommunitiesFacade(community_queries),
    )
    connections_facade, publishing_facade = (
        ConnectionsFacade(connection_queries),
        PublishingFacade(publication_queries, publishing),
    )
    gateway = PublishingGateway(publishing_facade)
    snapshot_queries = SnapshotQueries(snapshots, gateway)
    strategies = {s.name: s for s in (ChronologicalStrategy(), DiverseGreedyStrategy())}
    return Services(
        profile_queries,
        PreferenceCommands(profiles, profile_queries, CommunityTopics(communities_facade)),
        connection_queries,
        ConnectionCommands(connections, ConnectionActors(profiles_facade), historical),
        community_queries,
        MembershipCommands(communities, community_queries, CommunityActors(profiles_facade), clock),
        publication_queries,
        PublicationCommands(
            publishing,
            publication_queries,
            PublishingActors(profiles_facade),
            CommunityPermits(communities_facade),
            clock,
        ),
        PublicationDiffusion(publication_queries, PublicationNetwork(network_facade)),
        snapshot_queries,
        FeedCommands(
            snapshots,
            snapshot_queries,
            ProfileGateway(profiles_facade),
            ConnectionGateway(connections_facade),
            CommunityGateway(communities_facade),
            gateway,
            strategies,
            clock,
        ),
        profiles_facade.actor,
        network_queries,
        StructuralQueries(DynamoStructuralResults(storage["network_analysis"]), datasets),
    )


def create_app(services, *, local_demo=False, storage_name="DynamoDB Local"):
    app = http_application(local_demo, storage_name=storage_name)
    for name in services.__dataclass_fields__:
        setattr(app.state, name, getattr(services, name))
    for router in (
        profiles_router,
        connections_router,
        communities_router,
        publishing_router,
        discovery_router,
        network_router,
    ):
        app.include_router(router)
    from .shared.interfaces.http.documentation import configure_openapi

    configure_openapi(app)
    return app


def compose_import(storage, *, workers=4, progress=None):
    from urllib.parse import urlparse

    if not isinstance(storage, PostgresPersistence):
        endpoint = urlparse(storage.client.meta.endpoint_url)
        if endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("La importación de simulaciones requiere almacenamiento local")
        for repository in storage.repositories.values():
            if not repository.table.startswith(("Outspark-local-", "Outspark-local-test-")):
                raise ValueError("Tabla de importación local no permitida")
    profiles = DynamoProfilesRepository(storage["profiles"], UnitOfWork(storage))
    facade = ProfilesFacade(ProfileQueries(profiles), ImportedProfiles(profiles))
    return ImportDataset(
        DynamoDatasetImporter(storage["network_analysis"], workers=workers, progress=progress),
        ProfileProvisioning(facade),
    )
