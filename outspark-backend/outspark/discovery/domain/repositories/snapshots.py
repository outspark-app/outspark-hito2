from typing import Protocol


class SnapshotsRepository(Protocol):
    def snapshot(self, snapshot_id: str) -> dict | None: ...
    def save(
        self,
        viewer: str,
        cards: list[dict],
        instant: str,
        strategy: str,
        metadata: dict,
        guards: tuple,
    ) -> str: ...
