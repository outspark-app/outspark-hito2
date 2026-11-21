from outspark.shared.application.contracts import ConsistencyGuard
from outspark.shared.application.errors import UseCaseError
from outspark.shared.domain.value_objects import identifier

from ...domain.repositories.profiles import ProfilesRepository


class ProfileQueries:
    def __init__(self, repository: ProfilesRepository):
        self.repository = repository

    def active(self, actor):
        profile = self.repository.profile(identifier(actor))
        if not profile or profile["status"] != "ACTIVE":
            raise UseCaseError(403, "inactive_account", "Cuenta inactiva o no provisionada.")
        return profile

    def me(self, actor):
        return {"profile": self.active(actor), "preferences": self.repository.preferences(actor)}

    def active_guard(self, actor):
        self.active(actor)
        return ConsistencyGuard("profiles", "active", actor)
