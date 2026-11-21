from typing import Protocol


class SimulationProfiles(Protocol):
    def provision(self, nodes: list[int], source: str) -> dict: ...
