"""Approach lifecycle events for UltraWideLock Matter devices."""

from datetime import UTC, datetime
from typing import Any

from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    APPROACH_CM_ATTRIBUTE_ID,
    CONF_CREDENTIAL_NAMES,
    CREDENTIAL_ID_ATTRIBUTE_ID,
    CUSTOM_CLUSTER_ID,
    DEVICE_IN_RANGE_ATTRIBUTE_ID,
    DISTANCE_MM_ATTRIBUTE_ID,
    DOOR_LOCK_CLUSTER_ID,
    DOMAIN,
    ENDPOINT_ID,
    LOCK_STATE_ATTRIBUTE_ID,
    UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID,
)
from .entity import UwbMatterEntity, async_setup_uwb_entities
from .history import UwbHistoryStore

EVENT_TYPES = [
    "device_detected",
    "approach_started",
    "unlock_threshold_crossed",
    "unlocked",
    "approach_aborted",
    "left_without_unlock",
    "left_after_unlock",
    "device_left_range",
    "relocked",
    "data_stale",
    "data_restored",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one approach event entity per UltraWideLock."""
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((CUSTOM_CLUSTER_ID, DEVICE_IN_RANGE_ATTRIBUTE_ID),),
        UwbEvent,
    )


class UwbEvent(UwbMatterEntity, EventEntity):
    """Publish UWB session, threshold, lock, and data-health transitions."""

    _attr_name = "UWB event"
    _attr_event_types = EVENT_TYPES

    def __init__(
        self, hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
    ) -> None:
        """Initialize cached session state."""
        super().__init__(hass, node_id, cluster_id, attribute_id)
        self._paths = {
            "credential": self._path(CUSTOM_CLUSTER_ID, CREDENTIAL_ID_ATTRIBUTE_ID),
            "distance": self._path(CUSTOM_CLUSTER_ID, DISTANCE_MM_ATTRIBUTE_ID),
            "approach": self._path(CUSTOM_CLUSTER_ID, APPROACH_CM_ATTRIBUTE_ID),
            "unlock": self._path(
                CUSTOM_CLUSTER_ID, UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID
            ),
            "lock": self._path(DOOR_LOCK_CLUSTER_ID, LOCK_STATE_ATTRIBUTE_ID),
        }
        attributes = self._node_attributes()
        self._credential = self._integer(attributes.get(self._paths["credential"]))
        self._distance_mm = self._integer(attributes.get(self._paths["distance"]))
        self._approach_cm = self._integer(attributes.get(self._paths["approach"]))
        self._unlock_cm = self._integer(attributes.get(self._paths["unlock"]))
        self._lock_state = self._integer(attributes.get(self._paths["lock"]))
        self._session_started: datetime | None = None
        self._minimum_mm: int | None = None
        self._approach_active = False
        self._device_detected = False
        self._unlock_crossed = False
        self._unlocked = False
        self._has_live_distance = False
        self._last_session: dict[str, Any] | None = None
        self._history: UwbHistoryStore = hass.data[DOMAIN]
        self._data_status = self._history.freshness_status(node_id)

    @staticmethod
    def _integer(value: object) -> int | None:
        """Return a Matter integer or None."""
        return value if isinstance(value, int) else None

    @staticmethod
    def _path(cluster_id: int, attribute_id: int) -> str:
        """Create one Matter attribute path."""
        return create_attribute_path(ENDPOINT_ID, cluster_id, attribute_id)

    def _node_attributes(self) -> dict[str, Any]:
        """Return the node's current raw attribute cache."""
        return self._matter.matter_client.get_node(
            self._node_id
        ).node_data.attributes

    async def async_added_to_hass(self) -> None:
        """Subscribe to every attribute used by the event state machine."""
        await super().async_added_to_hass()
        for name, path in self._paths.items():
            self.async_on_remove(
                self._matter.matter_client.subscribe_events(
                    callback=lambda event, data, name=name: self._updated(name, data),
                    event_filter=EventType.ATTRIBUTE_UPDATED,
                    node_filter=self._node_id,
                    attr_path_filter=path,
                )
            )
        self.async_on_remove(
            self._history.subscribe_freshness(self._freshness_updated)
        )
        self._presence_updated(bool(self._value))

    def _freshness_updated(self, node_id: int) -> None:
        """Publish loss and restoration of the live UWB data stream."""
        if node_id != self._node_id:
            return
        previous = self._data_status
        self._data_status = self._history.freshness_status(node_id)
        if self._data_status == "stale" and previous != "stale":
            self._emit("data_stale")
        elif self._data_status == "live" and previous == "stale":
            self._emit("data_restored")

    def _attribute_updated(self, event: EventType, data: object) -> None:
        """Handle the presence attribute subscribed by the base entity."""
        super()._attribute_updated(event, data)
        self._updated("presence", data)

    def _updated(self, name: str, data: object) -> None:
        """Advance the session state after one Matter attribute update."""
        if name == "presence":
            self._presence_updated(bool(data))
            return
        value = self._integer(data)
        if name == "credential":
            self._credential = value if value else None
            self._distance_updated()
        elif name == "distance":
            self._distance_mm = value
            self._has_live_distance = True
            self._distance_updated()
        elif name == "approach":
            self._approach_cm = value
            self._distance_updated()
        elif name == "unlock":
            self._unlock_cm = value
            self._distance_updated()
        elif name == "lock":
            previous = self._lock_state
            self._lock_state = value
            if value == 2 and previous != 2:
                self._unlocked = True
                self._emit("unlocked")
            elif value == 1 and previous == 2:
                event_data = (
                    self._event_data()
                    if self._session_started is not None
                    else self._last_session
                )
                self._emit("relocked", event_data)

    def _presence_updated(self, in_range: bool) -> None:
        """Start or finish an authenticated ranging session."""
        if in_range and self._session_started is None:
            attributes = self._node_attributes()
            self._credential = self._integer(
                attributes.get(self._paths["credential"])
            )
            self._distance_mm = self._integer(
                attributes.get(self._paths["distance"])
            )
            self._session_started = datetime.now(UTC)
            self._minimum_mm = self._distance_mm
            self._approach_active = False
            self._device_detected = False
            self._unlock_crossed = False
            self._unlocked = False
            self._has_live_distance = False
            self._distance_updated()
        elif not in_range and self._session_started is not None:
            if self._approach_active and not self._unlocked:
                self._emit("approach_aborted")
            self._emit(
                "left_after_unlock" if self._unlocked else "left_without_unlock"
            )
            self._emit("device_left_range")
            self._last_session = self._event_data()
            self._session_started = None
            self._minimum_mm = None
            self._approach_active = False
            self._device_detected = False
            self._unlock_crossed = False
            self._unlocked = False
            self._has_live_distance = False

    def _distance_updated(self) -> None:
        """Detect approach and unlock-distance boundary crossings."""
        if (
            self._session_started is None
            or self._credential is None
            or self._distance_mm is None
            or not self._has_live_distance
        ):
            return
        if self._minimum_mm is None or self._distance_mm < self._minimum_mm:
            self._minimum_mm = self._distance_mm
        if not self._device_detected:
            self._device_detected = True
            self._emit("device_detected")
        if self._approach_cm is not None:
            inside_approach = self._distance_mm <= self._approach_cm * 10
            if inside_approach and not self._approach_active:
                self._approach_active = True
                self._emit("approach_started")
            elif not inside_approach and self._approach_active and not self._unlocked:
                self._approach_active = False
                self._emit("approach_aborted")
        if self._unlock_cm is not None:
            inside_unlock = self._distance_mm <= self._unlock_cm * 10
            if inside_unlock and not self._unlock_crossed:
                self._unlock_crossed = True
                self._emit("unlock_threshold_crossed")

    def _credential_label(self) -> str | None:
        """Resolve the current pseudonymous credential to its friendly name."""
        if self._credential is None:
            return None
        credential_id = f"{self._credential:08X}"
        entry = self._config_entry
        if entry is not None:
            if name := entry.options.get(CONF_CREDENTIAL_NAMES, {}).get(
                credential_id, ""
            ):
                return name
        return f"Unknown ({credential_id})"

    def _event_data(self) -> dict[str, Any]:
        """Build consistent automation data for the current session."""
        duration = (
            (datetime.now(UTC) - self._session_started).total_seconds()
            if self._session_started is not None
            else None
        )
        return {
            "credential_name": self._credential_label(),
            "credential_id": (
                f"{self._credential:08X}" if self._credential is not None else None
            ),
            "distance_cm": (
                round(self._distance_mm / 10, 1)
                if self._distance_mm is not None
                else None
            ),
            "minimum_distance_cm": (
                round(self._minimum_mm / 10, 1)
                if self._minimum_mm is not None
                else None
            ),
            "session_duration_s": round(duration, 1) if duration is not None else None,
            "approach_started": self._approach_active,
            "unlock_threshold_crossed": self._unlock_crossed,
            "unlocked": self._unlocked,
            "data_status": self._data_status,
        }

    def _emit(
        self, event_type: str, event_data: dict[str, Any] | None = None
    ) -> None:
        """Publish one Home Assistant event entity transition."""
        self._trigger_event(event_type, event_data or self._event_data())
        self.schedule_update_ha_state()
