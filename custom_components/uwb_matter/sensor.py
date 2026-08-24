"""Sensors for UltraWideLock Matter devices."""

from datetime import datetime

from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CREDENTIAL_NAMES,
    CREDENTIAL_ID_ATTRIBUTE_ID,
    CUSTOM_CLUSTER_ID,
    DISTANCE_MM_ATTRIBUTE_ID,
    DOOR_LOCK_CLUSTER_ID,
    DOMAIN,
    ENDPOINT_ID,
    LOCK_STATE_ATTRIBUTE_ID,
    MOVEMENT_STATE_ATTRIBUTE_ID,
)
from .entity import UwbMatterEntity, async_setup_uwb_entities
from .history import HistoryRecord, UwbHistoryStore


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UltraWideLock sensors."""
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        (
            (CUSTOM_CLUSTER_ID, DISTANCE_MM_ATTRIBUTE_ID),
            (CUSTOM_CLUSTER_ID, CREDENTIAL_ID_ATTRIBUTE_ID),
            (CUSTOM_CLUSTER_ID, MOVEMENT_STATE_ATTRIBUTE_ID),
        ),
        _sensor_factory,
    )
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((CUSTOM_CLUSTER_ID, CREDENTIAL_ID_ATTRIBUTE_ID),),
        UwbLastSeenSensor,
    )
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((CUSTOM_CLUSTER_ID, CREDENTIAL_ID_ATTRIBUTE_ID),),
        UwbLastSeenAtSensor,
    )
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((DOOR_LOCK_CLUSTER_ID, LOCK_STATE_ATTRIBUTE_ID),),
        UwbLastUnlockedSensor,
    )
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((DOOR_LOCK_CLUSTER_ID, LOCK_STATE_ATTRIBUTE_ID),),
        UwbLastUnlockedAtSensor,
    )
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((DOOR_LOCK_CLUSTER_ID, LOCK_STATE_ATTRIBUTE_ID),),
        UwbLastUnlockedDistanceSensor,
    )


def _sensor_factory(
    hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
) -> UwbMatterEntity:
    """Create the entity belonging to a custom sensor attribute."""
    entity_class = {
        DISTANCE_MM_ATTRIBUTE_ID: UwbDistanceSensor,
        CREDENTIAL_ID_ATTRIBUTE_ID: UwbCredentialIdSensor,
        MOVEMENT_STATE_ATTRIBUTE_ID: UwbMovementStateSensor,
    }[attribute_id]
    return entity_class(hass, node_id, cluster_id, attribute_id)


class UwbDistanceSensor(UwbMatterEntity, SensorEntity):
    """Live authenticated UWB distance."""

    _attr_name = "UWB distance"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return distance in centimetres."""
        return self._value / 10 if isinstance(self._value, int) else None


class UwbMovementStateSensor(UwbMatterEntity, SensorEntity):
    """Filtered movement direction of the currently ranged credential."""

    _attr_name = "UWB movement"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["unknown", "stationary", "approaching", "leaving"]

    @property
    def native_value(self) -> str:
        """Return a stable state name for the firmware enum."""
        if isinstance(self._value, int) and 0 <= self._value < len(self._attr_options):
            return self._attr_options[self._value]
        return "unknown"


class UwbCredentialIdSensor(UwbMatterEntity, SensorEntity):
    """Stable pseudonymous identifier for the ranged credential."""

    _attr_name = "UWB credential"

    async def async_added_to_hass(self) -> None:
        """Subscribe and persist an initially active credential."""
        await super().async_added_to_hass()
        self._remember_credential()

    def _attribute_updated(self, event: object, data: object) -> None:
        """Update the entity and remember newly observed credentials."""
        super()._attribute_updated(event, data)
        self._remember_credential()

    def _credential_id(self) -> str | None:
        """Return the current credential as hexadecimal text."""
        if not isinstance(self._value, int) or self._value == 0:
            return None
        return f"{self._value:08X}"

    def _remember_credential(self) -> None:
        """Persist a credential ID the first time it is observed."""
        credential_id = self._credential_id()
        entry = self._config_entry
        if credential_id is None or entry is None:
            return
        names = dict(entry.options.get(CONF_CREDENTIAL_NAMES, {}))
        if credential_id in names:
            return
        names[credential_id] = ""
        self._hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_CREDENTIAL_NAMES: names},
        )

    @property
    def native_value(self) -> str | None:
        """Return a friendly name or an identifiable unknown value."""
        credential_id = self._credential_id()
        if credential_id is None:
            return None
        entry = self._config_entry
        if entry is not None:
            name = entry.options.get(CONF_CREDENTIAL_NAMES, {}).get(
                credential_id, ""
            )
            if name:
                return name
        return f"Unknown ({credential_id})"

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Keep the raw pseudonymous ID available for diagnostics."""
        credential_id = self._credential_id()
        return {"credential_id": credential_id} if credential_id else None


class UwbHistorySensor(UwbMatterEntity, SensorEntity):
    """Base for a persisted credential history sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _history_kind: str
    _history_entity_key: str | None = None

    def __init__(
        self, hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
    ) -> None:
        """Initialize a history sensor."""
        super().__init__(hass, node_id, cluster_id, attribute_id)
        self._history: UwbHistoryStore = hass.data[DOMAIN]
        self._record = self._history.get_record(node_id, self._history_kind)
        history_key = self._history_entity_key or self._history_kind
        self._attr_unique_id = f"{self._attr_unique_id}-history-{history_key}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to Matter and shared history updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self._history.subscribe(self._history_updated))

    def _history_updated(
        self, node_id: int, kind: str, record: HistoryRecord
    ) -> None:
        """Refresh when another entity writes this history record."""
        if node_id == self._node_id and kind == self._history_kind:
            self._record = record
            self.schedule_update_ha_state()

    def _credential_label(self, credential_id: str | None) -> str:
        """Resolve a stored credential ID to its friendly name."""
        if credential_id is None:
            return "Unknown source"
        entry = self._config_entry
        if entry is not None:
            name = entry.options.get(CONF_CREDENTIAL_NAMES, {}).get(
                credential_id, ""
            )
            if name:
                return name
        return f"Unknown ({credential_id})"

    @property
    def native_value(self) -> str | None:
        """Return the credential associated with this history record."""
        if self._record is None:
            return None
        return self._credential_label(self._record["credential_id"])

    @property
    def extra_state_attributes(self) -> dict[str, str | None] | None:
        """Expose machine-readable history details."""
        if self._record is None:
            return None
        return {
            "credential_id": self._record["credential_id"],
            "timestamp": self._record["timestamp"],
        }


class UwbLastSeenSensor(UwbHistorySensor):
    """Last credential observed by this lock."""

    _attr_name = "Last device seen"
    _history_kind = "last_seen"

    def __init__(
        self, hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
    ) -> None:
        """Initialize completed-session tracking."""
        super().__init__(hass, node_id, cluster_id, attribute_id)
        credential = self._value
        self._active_credential = (
            credential
            if isinstance(credential, int) and credential != 0
            else None
        )

    def _attribute_updated(self, event: EventType, data: object) -> None:
        """Record the previous credential when its session ends."""
        super()._attribute_updated(event, data)
        new_credential = data if isinstance(data, int) and data != 0 else None
        if (
            self._active_credential is not None
            and new_credential != self._active_credential
        ):
            self._record = self._history.record_seen(
                self._node_id, self._active_credential
            )
            self.schedule_update_ha_state()
        self._active_credential = new_credential


class UwbHistoryTimestampSensor(UwbHistorySensor):
    """Timestamp belonging to a persisted credential history record."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the history timestamp."""
        if self._record is None:
            return None
        return dt_util.parse_datetime(self._record["timestamp"])


class UwbLastSeenAtSensor(UwbHistoryTimestampSensor):
    """Time the previous credential session ended."""

    _attr_name = "Last device seen at"
    _history_kind = "last_seen"
    _history_entity_key = "last_seen_at"


class UwbLastUnlockedSensor(UwbHistorySensor):
    """Credential present when this lock last became unlocked."""

    _attr_name = "Last device unlocked"
    _history_kind = "last_unlocked"

    def __init__(
        self, hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
    ) -> None:
        """Initialize unlock attribution."""
        super().__init__(hass, node_id, cluster_id, attribute_id)
        credential_path = create_attribute_path(
            ENDPOINT_ID, CUSTOM_CLUSTER_ID, CREDENTIAL_ID_ATTRIBUTE_ID
        )
        credential = self._matter.matter_client.get_node(
            node_id
        ).node_data.attributes.get(credential_path)
        self._current_credential = credential if isinstance(credential, int) else None
        self._credential_path = credential_path
        distance_path = create_attribute_path(
            ENDPOINT_ID, CUSTOM_CLUSTER_ID, DISTANCE_MM_ATTRIBUTE_ID
        )
        distance = self._matter.matter_client.get_node(
            node_id
        ).node_data.attributes.get(distance_path)
        self._current_distance_mm = distance if isinstance(distance, int) else None
        self._distance_path = distance_path

    async def async_added_to_hass(self) -> None:
        """Subscribe to both LockState and the current credential."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._matter.matter_client.subscribe_events(
                callback=self._credential_updated,
                event_filter=EventType.ATTRIBUTE_UPDATED,
                node_filter=self._node_id,
                attr_path_filter=self._credential_path,
            )
        )
        self.async_on_remove(
            self._matter.matter_client.subscribe_events(
                callback=self._distance_updated,
                event_filter=EventType.ATTRIBUTE_UPDATED,
                node_filter=self._node_id,
                attr_path_filter=self._distance_path,
            )
        )

    def _credential_updated(self, event: EventType, data: object) -> None:
        """Track the credential currently in ranging range."""
        self._current_credential = (
            data if isinstance(data, int) and data != 0 else None
        )

    def _distance_updated(self, event: EventType, data: object) -> None:
        """Track the current ranging distance in millimetres."""
        self._current_distance_mm = data if isinstance(data, int) else None

    def _attribute_updated(self, event: EventType, data: object) -> None:
        """Attribute an unlocked transition to the current credential."""
        previous = self._value
        super()._attribute_updated(event, data)
        if isinstance(data, int) and data == 2 and previous != 2:
            self._record = self._history.record_unlock(
                self._node_id,
                self._current_credential,
                self._current_distance_mm,
            )
            self.schedule_update_ha_state()


class UwbLastUnlockedAtSensor(UwbHistoryTimestampSensor):
    """Time the lock most recently transitioned to unlocked."""

    _attr_name = "Last device unlocked at"
    _history_kind = "last_unlocked"
    _history_entity_key = "last_unlocked_at"


class UwbLastUnlockedDistanceSensor(UwbHistorySensor):
    """Distance measured at the most recent unlock transition."""

    _attr_name = "Last unlocked at distance"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS
    _attr_suggested_display_precision = 1
    _history_kind = "last_unlocked"
    _history_entity_key = "last_unlocked_distance"

    @property
    def native_value(self) -> float | None:
        """Return the last unlock distance in centimetres."""
        if self._record is None:
            return None
        distance_mm = self._record.get("distance_mm")
        return distance_mm / 10 if isinstance(distance_mm, int) else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None] | None:
        """Expose the timestamp and credential associated with the distance."""
        if self._record is None:
            return None
        return {
            "credential_id": self._record["credential_id"],
            "timestamp": self._record["timestamp"],
        }
