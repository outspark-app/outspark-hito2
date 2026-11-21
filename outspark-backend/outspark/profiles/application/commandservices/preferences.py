from ...domain.model.aggregates import Preferences
from ...domain.repositories.profiles import ProfilesRepository
from ..outboundservices.topics import TopicCatalog


class PreferenceCommands:
    def __init__(self, repository: ProfilesRepository, queries, topics: TopicCatalog):
        self.repository, self.queries, self.topics = repository, queries, topics

    def change(self, actor, topics, version):
        preferences = Preferences.change(actor, topics, version)
        guards = (self.queries.active_guard(actor), *self.topics.validate(list(preferences.topics)))
        return self.repository.save_preferences(preferences, guards)
