from typing import Protocol


class Actors(Protocol):
    def active_guard(self, actor: str): ...
