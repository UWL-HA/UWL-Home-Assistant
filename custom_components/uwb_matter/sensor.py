"""Sensors for UltraWideLock Matter devices."""

from datetime import datetime
from time import monotonic

from homeassistant.components import persistent_notification
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType, MatterNodeEvent

from .binding import door_lock_bindings, matter_lock_name
from .const import (
    BINDING_ATTRIBUTE_ID,
    BINDING_CLUSTER_ID,
    CONF_CREDENTIAL_NAMES,
    CONF_CREDENTIAL_PRESENCE,
    CREDENTIAL_ID_ATTRIBUTE_ID,
    CUSTOM_CLUSTER_ID,
    DEVICE_IN_RANGE_ATTRIBUTE_ID,
    DISTANCE_MM_ATTRIBUTE_ID,
    DOMAIN,
    DOOR_LOCK_CLUSTER_ID,
    ENDPOINT_ID,
    LOCK_OPERATION_EVENT_ID,
    LOCK_STATE_ATTRIBUTE_ID,
    MOVEMENT_STATE_ATTRIBUTE_ID,
    ULTRAWIDELOCK_UNLOCK_ATTRIBUTE_ID,
    UNLOCK_OPERATION_TYPES,
    UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID,
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
        ((CUSTOM_CLUSTER_ID, DEVICE_IN_RANGE_ATTRIBUTE_ID),),
        UwbDataStatusSensor,
    )
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((CUSTOM_CLUSTER_ID, DEVICE_IN_RANGE_ATTRIBUTE_ID),),
        UwbLastUpdateSensor,
    )
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((BINDING_CLUSTER_ID, BINDING_ATTRIBUTE_ID),),
        UwbBoundLocksSensor,
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


class UwbFreshnessAwareSensor(UwbMatterEntity, SensorEntity):
    """Base for live values that must clear when their feed becomes stale."""


    async def async_added_to_hass(self) -> None:
        """Subscribe to both Matter values and local freshness changes."""
        await super().async_added_to_hass()
        history: UwbHistoryStore = self._hass.data[DOMAIN]
        self.async_on_remove(history.subscribe_freshness(self._freshness_updated))

    def _freshness_updated(self, node_id: int) -> None:
        """Refresh this entity when its node becomes stale or live."""
        if node_id == self._node_id:
            self.schedule_update_ha_state()

    @property
    def _uwb_value_is_fresh(self) -> bool:
        history: UwbHistoryStore = self._hass.data[DOMAIN]
        return history.attribute_is_fresh(self._node_id, self._attribute_id)


class UwbDistanceSensor(UwbFreshnessAwareSensor):
    """Live authenticated UWB distance."""

    _attr_name = "UWB distance"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return distance in centimetres."""
        return (
            self._value / 10
            if self._uwb_value_is_fresh and isinstance(self._value, int)
            else None
        )


class UwbMovementStateSensor(UwbFreshnessAwareSensor):
    """Filtered movement direction of the currently ranged credential."""

    _attr_name = "UWB movement"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["unknown", "stationary", "approaching", "leaving"]

    @property
    def native_value(self) -> str | None:
        """Return a stable state name for the firmware enum."""
        if (
            self._uwb_value_is_fresh
            and isinstance(self._value, int)
            and 0 <= self._value < len(self._attr_options)
        ):
            return self._attr_options[self._value]
        return None


class UwbFreshnessSensor(UwbMatterEntity, SensorEntity):
    """Base for local UWB subscription-health entities."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
    ) -> None:
        """Initialize a uniquely identified freshness entity."""
        super().__init__(hass, node_id, cluster_id, attribute_id)
        self._history: UwbHistoryStore = hass.data[DOMAIN]

    async def async_added_to_hass(self) -> None:
        """Subscribe to local freshness state."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._history.subscribe_freshness(self._freshness_updated)
        )

    def _freshness_updated(self, node_id: int) -> None:
        """Refresh when this node receives data or reaches its deadline."""
        if node_id == self._node_id:
            self.schedule_update_ha_state()


class UwbDataStatusSensor(UwbFreshnessSensor):
    """Subscription freshness of the live UWB data stream."""

    _attr_name = "UWB data status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["live", "stale", "unavailable"]

    def __init__(
        self, hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
    ) -> None:
        super().__init__(hass, node_id, cluster_id, attribute_id)
        self._attr_unique_id = f"{self._attr_unique_id}-freshness-status"

    @property
    def available(self) -> bool:
        """Keep the diagnostic itself available when its Matter node is not."""
        return True

    @property
    def native_value(self) -> str:
        """Return live, stale, or unavailable."""
        node = self._matter.matter_client.get_node(self._node_id)
        if not node.available:
            return "unavailable"
        return self._history.freshness_status(self._node_id)


class UwbLastUpdateSensor(UwbFreshnessSensor):
    """Timestamp of the latest live UWB subscription update."""

    _attr_name = "Last UWB update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
    ) -> None:
        super().__init__(hass, node_id, cluster_id, attribute_id)
        self._attr_unique_id = f"{self._attr_unique_id}-freshness-last-update"

    @property
    def native_value(self) -> datetime | None:
        """Return the most recent UWB update timestamp."""
        return self._history.last_uwb_update(self._node_id)


class UwbBoundLocksSensor(UwbMatterEntity, SensorEntity):
    """Door Lock targets in this node's standard Matter binding table."""

    _attr_name = "Bound lock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return a friendly summary of bound Door Lock targets."""
        bindings = door_lock_bindings(self._value)
        if not bindings:
            return "None"
        registry = er.async_get(self._hass)
        names = [
            matter_lock_name(
                self._hass,
                registry,
                target["node"],
                target["endpoint"],
            )
            for target in bindings
        ]
        return names[0] if len(names) == 1 else f"{len(names)} locks"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose every resolved binding target."""
        bindings = door_lock_bindings(self._value)
        registry = er.async_get(self._hass)
        targets = [
            {
                **target,
                "name": matter_lock_name(
                    self._hass,
                    registry,
                    target["node"],
                    target["endpoint"],
                ),
            }
            for target in bindings
        ]
        return {"bindings": targets, "count": len(targets)}


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
        presence = dict(
            entry.options.get(CONF_CREDENTIAL_PRESENCE, {})
        )
        presence[credential_id] = True
        persistent_notification.async_create(
            self._hass,
            (
                f"A new UWB credential (`{credential_id}`) was detected. "
                "Give it a friendly name, or disable its occupancy sensor, "
                "in **Settings > Devices & services > UltraWideLock > Configure**.\n\n"
                "[Open UltraWideLock settings]"
                "(/config/integrations/integration/uwb_matter)"
            ),
            title="New UltraWideLock device detected",
            notification_id=f"uwb_matter_new_credential_{credential_id}",
        )
        self._hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_CREDENTIAL_NAMES: names,
                CONF_CREDENTIAL_PRESENCE: presence,
            },
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
        unlock_threshold_path = create_attribute_path(
            ENDPOINT_ID, CUSTOM_CLUSTER_ID, UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID
        )
        unlock_threshold = self._matter.matter_client.get_node(
            node_id
        ).node_data.attributes.get(unlock_threshold_path)
        self._unlock_threshold_cm = (
            unlock_threshold if isinstance(unlock_threshold, int) else None
        )
        self._unlock_threshold_path = unlock_threshold_path
        unlock_enabled_path = create_attribute_path(
            ENDPOINT_ID, CUSTOM_CLUSTER_ID, ULTRAWIDELOCK_UNLOCK_ATTRIBUTE_ID
        )
        unlock_enabled = self._matter.matter_client.get_node(
            node_id
        ).node_data.attributes.get(unlock_enabled_path)
        self._unlock_enabled = bool(unlock_enabled)
        self._unlock_enabled_path = unlock_enabled_path
        self._session_unlock_recorded = False
        self._last_unlock_record_at = 0.0

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
        for path, callback in (
            (self._unlock_threshold_path, self._unlock_threshold_updated),
            (self._unlock_enabled_path, self._unlock_enabled_updated),
        ):
            self.async_on_remove(
                self._matter.matter_client.subscribe_events(
                    callback=callback,
                    event_filter=EventType.ATTRIBUTE_UPDATED,
                    node_filter=self._node_id,
                    attr_path_filter=path,
                )
            )
        self.async_on_remove(
            self._matter.matter_client.subscribe_events(
                callback=self._node_event,
                event_filter=EventType.NODE_EVENT,
                node_filter=self._node_id,
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
        credential = (
            data if isinstance(data, int) and data != 0 else None
        )
        if credential != self._current_credential:
            self._session_unlock_recorded = False
        self._current_credential = credential
        self._record_threshold_unlock_if_needed()

    def _distance_updated(self, event: EventType, data: object) -> None:
        """Track the current ranging distance in millimetres."""
        self._current_distance_mm = data if isinstance(data, int) else None
        self._record_threshold_unlock_if_needed()

    def _unlock_threshold_updated(self, event: EventType, data: object) -> None:
        """Track the live unlock threshold."""
        self._unlock_threshold_cm = data if isinstance(data, int) else None

    def _unlock_enabled_updated(self, event: EventType, data: object) -> None:
        """Track whether UWB may unlock UltraWideLock itself."""
        self._unlock_enabled = bool(data)

    def _record_threshold_unlock_if_needed(self) -> None:
        """Record one UWB unlock trigger per credential session."""
        if (
            self._session_unlock_recorded
            or not self._unlock_enabled
            or self._current_credential is None
            or self._current_distance_mm is None
            or self._unlock_threshold_cm is None
            or self._current_distance_mm > self._unlock_threshold_cm * 10
        ):
            return
        self._session_unlock_recorded = True
        self._record_current_unlock()

    def _node_event(self, event: EventType, data: MatterNodeEvent) -> None:
        """Record every native Door Lock unlock operation."""
        if (
            data.endpoint_id != ENDPOINT_ID
            or data.cluster_id != DOOR_LOCK_CLUSTER_ID
            or data.event_id != LOCK_OPERATION_EVENT_ID
            or not data.data
            or data.data.get("lockOperationType") not in UNLOCK_OPERATION_TYPES
        ):
            return
        now = monotonic()
        if now - self._last_unlock_record_at <= 2:
            return
        self._record_current_unlock()

    def _record_current_unlock(self) -> None:
        """Store an unlock with the currently ranged credential and distance."""
        self._last_unlock_record_at = monotonic()
        self._record = self._history.record_unlock(
            self._node_id,
            self._current_credential,
            self._current_distance_mm,
        )
        self.schedule_update_ha_state()

    def _attribute_updated(self, event: EventType, data: object) -> None:
        """Use an unlocked state transition when no operation event arrives."""
        previous = self._value
        super()._attribute_updated(event, data)
        if (
            isinstance(data, int)
            and data == 2
            and previous != 2
            and monotonic() - self._last_unlock_record_at > 2
        ):
            self._record_current_unlock()


class UwbLastUnlockedAtSensor(UwbHistoryTimestampSensor):
    """Time of the lock's most recent unlock operation."""

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
