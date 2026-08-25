"""Persistent local history for UltraWideLock credential observations."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import NotRequired, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .const import DEFAULT_STALE_TIMEOUT, DEVICE_IN_RANGE_ATTRIBUTE_ID

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
        self._hass = hass
        self._data: dict = {"nodes": {}}
        self._listeners: set[Callable[[int, str, HistoryRecord], None]] = set()
        self.credential_names: dict[str, str] = {}
        self.credential_presence: dict[str, bool] = {}
        self.stale_timeout = DEFAULT_STALE_TIMEOUT
        self._freshness: dict[int, dict] = {}
        self._freshness_listeners: set[Callable[[int], None]] = set()
        self._stale_timers: dict[int, Callable[[], None]] = {}

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

    def initialize_freshness(self, node_id: int, in_range: bool) -> None:
        """Initialize runtime freshness without trusting cached data as fresh."""
        self._freshness.setdefault(
            node_id,
            {
                "in_range": in_range,
                "status": "unavailable",
                "last_update": None,
                "updated_attributes": set(),
            },
        )

    def mark_uwb_update(
        self, node_id: int, attribute_id: int, value: object
    ) -> None:
        """Record a live UWB subscription update and refresh its stale timer."""
        state = self._freshness.setdefault(
            node_id,
            {
                "in_range": False,
                "status": "unavailable",
                "last_update": None,
                "updated_attributes": set(),
            },
        )
        state["last_update"] = datetime.now(UTC)
        if attribute_id == DEVICE_IN_RANGE_ATTRIBUTE_ID:
            was_in_range = state["in_range"]
            state["in_range"] = bool(value)
            if state["in_range"] and not was_in_range:
                state["updated_attributes"].clear()
        state["updated_attributes"].add(attribute_id)
        if not state["in_range"]:
            state["status"] = "unavailable"
            self._cancel_stale_timer(node_id)
        else:
            state["status"] = "live"
            self._schedule_stale_timer(node_id)
        self._notify_freshness(node_id)

    def freshness_status(self, node_id: int) -> str:
        """Return live, stale, or unavailable for one node."""
        return self._freshness.get(node_id, {}).get("status", "unavailable")

    def last_uwb_update(self, node_id: int) -> datetime | None:
        """Return the most recent live UWB attribute update."""
        return self._freshness.get(node_id, {}).get("last_update")

    def attribute_is_fresh(self, node_id: int, attribute_id: int) -> bool:
        """Return whether an attribute updated during the current live session."""
        state = self._freshness.get(node_id, {})
        return (
            state.get("status") == "live"
            and attribute_id in state.get("updated_attributes", set())
        )

    def subscribe_freshness(
        self, listener: Callable[[int], None]
    ) -> Callable[[], None]:
        """Subscribe to freshness state changes."""
        self._freshness_listeners.add(listener)

        def unsubscribe() -> None:
            self._freshness_listeners.discard(listener)

        return unsubscribe

    def shutdown(self) -> None:
        """Cancel runtime timers when the integration unloads."""
        for cancel in self._stale_timers.values():
            cancel()
        self._stale_timers.clear()

    def _schedule_stale_timer(self, node_id: int) -> None:
        """Restart the deadline for one active ranging session."""
        self._cancel_stale_timer(node_id)

        def mark_stale(_now: datetime) -> None:
            self._stale_timers.pop(node_id, None)
            state = self._freshness.get(node_id)
            if state is not None and state["in_range"]:
                state["status"] = "stale"
                self._notify_freshness(node_id)

        self._stale_timers[node_id] = async_call_later(
            self._hass, self.stale_timeout, mark_stale
        )

    def _cancel_stale_timer(self, node_id: int) -> None:
        """Cancel a node's pending stale deadline."""
        if cancel := self._stale_timers.pop(node_id, None):
            cancel()

    def _notify_freshness(self, node_id: int) -> None:
        """Notify runtime freshness entities."""
        for listener in tuple(self._freshness_listeners):
            listener(node_id)

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
