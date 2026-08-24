"""Persistent local history for UltraWideLock credential observations."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import NotRequired, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

STORAGE_KEY = "uwb_matter.history"
STORAGE_VERSION = 1


class HistoryRecord(TypedDict):
    """A credential observation and its UTC timestamp."""

    credential_id: str | None
    timestamp: str
    distance_mm: NotRequired[int | None]


class UwbHistoryStore:
    """Store last-seen and last-unlock records per Matter node."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._store: Store[dict] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict = {"nodes": {}}
        self._listeners: set[Callable[[int, str, HistoryRecord], None]] = set()
        self.credential_names: dict[str, str] = {}

    async def async_load(self) -> None:
        """Load existing history."""
        if stored := await self._store.async_load():
            self._data = stored

    def get_record(self, node_id: int, kind: str) -> HistoryRecord | None:
        """Return one stored record."""
        return self._data.get("nodes", {}).get(str(node_id), {}).get(kind)

    def record_seen(self, node_id: int, credential_id: int) -> HistoryRecord:
        """Record an observed credential."""
        return self._record(node_id, "last_seen", f"{credential_id:08X}")

    def record_unlock(
        self,
        node_id: int,
        credential_id: int | None,
        distance_mm: int | None,
    ) -> HistoryRecord:
        """Record the credential present at an unlock transition."""
        formatted = f"{credential_id:08X}" if credential_id else None
        return self._record(
            node_id, "last_unlocked", formatted, distance_mm=distance_mm
        )

    def subscribe(
        self, listener: Callable[[int, str, HistoryRecord], None]
    ) -> Callable[[], None]:
        """Subscribe to history changes."""
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    def _record(
        self,
        node_id: int,
        kind: str,
        credential_id: str | None,
        *,
        distance_mm: int | None = None,
    ) -> HistoryRecord:
        """Save one record and schedule durable storage."""
        record: HistoryRecord = {
            "credential_id": credential_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if kind == "last_unlocked":
            record["distance_mm"] = distance_mm
        nodes = self._data.setdefault("nodes", {})
        nodes.setdefault(str(node_id), {})[kind] = record
        self._store.async_delay_save(lambda: self._data, 1)
        for listener in tuple(self._listeners):
            listener(node_id, kind, record)
        return record
