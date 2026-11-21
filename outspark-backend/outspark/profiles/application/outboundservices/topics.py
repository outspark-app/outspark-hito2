from typing import Protocol


class TopicCatalog(Protocol):
    def validate(self, topics: list[str]) -> tuple: ...
