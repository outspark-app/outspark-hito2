"""Outspark service for Cloud Run with Firebase identity and PostgreSQL."""

import hashlib
import os

import requests
from cachecontrol import CacheControl
from fastapi import Header
from google.auth import exceptions
from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_firebase_token
from starlette.middleware.cors import CORSMiddleware

from outspark.bootstrap import compose, create_app
from outspark.persistence import postgres_storage
from outspark.profiles.infrastructure.persistence.dynamodb.profiles import DynamoProfilesRepository
from outspark.shared.application.errors import UseCaseError
from outspark.shared.interfaces.http.dependencies import actor


class FirebaseActor:
    def __init__(self, project, profiles, active_policy):
        self.project = project
        self.profiles = profiles
        self.active_policy = active_policy
        self.transport = Request(session=CacheControl(requests.Session()))

    def __call__(self, authorization: str | None = Header(default=None)):
        scheme, _, token = (authorization or "").partition(" ")
        denied = UseCaseError(401, "authentication_required", "Inicia sesión en Outspark.")
        if scheme.lower() != "bearer" or not 1 <= len(token) <= 8192:
            raise denied
        try:
            claims = verify_firebase_token(token, self.transport, audience=self.project)
        except exceptions.TransportError as error:
            raise UseCaseError(
                503, "auth_unavailable", "Acceso temporalmente no disponible."
            ) from error
        except (ValueError, exceptions.GoogleAuthError) as error:
            raise denied from error
        uid = claims.get("sub")
        if (
            claims.get("iss") != f"https://securetoken.google.com/{self.project}"
            or claims.get("aud") != self.project
            or not isinstance(uid, str)
            or not 1 <= len(uid) <= 128
        ):
            raise denied
        key = hashlib.sha256(uid.encode()).hexdigest()[:59]
        user = "auth-" + key
        self.profiles.ensure_authenticated(user, "Persona " + key[:8])
        self.active_policy(user)
        return user


def application():
    project = os.environ["OUTSPARK_FIREBASE_PROJECT"]
    storage = postgres_storage(os.environ["OUTSPARK_POSTGRES_DSN"])
    services = compose(storage)
    api = create_app(services, storage_name="PostgreSQL")
    api.state.firebase = True
    api.description = (
        "Autentícate con un ID token de Firebase. La red histórica conserva el dataset "
        "de la simulación y las publicaciones de Outspark se guardan en PostgreSQL."
    )
    profiles = DynamoProfilesRepository(storage["profiles"], None)
    api.dependency_overrides[actor] = FirebaseActor(project, profiles, services.actor_policy)
    api.router.add_event_handler("shutdown", storage.close)
    return CORSMiddleware(
        api,
        allow_origins=[f"https://{project}.web.app", f"https://{project}.firebaseapp.com"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )
