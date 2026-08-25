"""Number controls for UltraWideLock Matter devices."""

from matter_server.common.helpers.util import create_attribute_path

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    APPROACH_CM_ATTRIBUTE_ID,
    AUTO_RELOCK_TIME_ATTRIBUTE_ID,
    CUSTOM_CLUSTER_ID,
    CONF_WRITABLE_CONTROLS,
    DOOR_LOCK_CLUSTER_ID,
    ENDPOINT_ID,
    MOTOR_MS_ATTRIBUTE_ID,
    RELOCK_CM_ATTRIBUTE_ID,
    UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID,
)
from .entity import UwbMatterEntity, async_setup_uwb_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UltraWideLock number controls."""
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((DOOR_LOCK_CLUSTER_ID, AUTO_RELOCK_TIME_ATTRIBUTE_ID),),
        UwbAutoRelockTimeNumber,
    )
    if entry.data.get(CONF_WRITABLE_CONTROLS, True):
        async_setup_uwb_entities(
            hass,
            entry,
            async_add_entities,
            (
                (CUSTOM_CLUSTER_ID, UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID),
                (CUSTOM_CLUSTER_ID, APPROACH_CM_ATTRIBUTE_ID),
                (CUSTOM_CLUSTER_ID, RELOCK_CM_ATTRIBUTE_ID),
                (CUSTOM_CLUSTER_ID, MOTOR_MS_ATTRIBUTE_ID),
            ),
            _uwb_config_number_factory,
        )


def _uwb_config_number_factory(
    hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
) -> UwbMatterEntity:
    """Create a writable UWB policy number."""
    entity_class = {
        UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID: UwbUnlockDistanceNumber,
        APPROACH_CM_ATTRIBUTE_ID: UwbApproachDistanceNumber,
        RELOCK_CM_ATTRIBUTE_ID: UwbRelockDistanceNumber,
        MOTOR_MS_ATTRIBUTE_ID: UwbMotorTimeNumber,
    }[attribute_id]
    return entity_class(hass, node_id, cluster_id, attribute_id)


class UwbConfigNumber(UwbMatterEntity, NumberEntity):
    """Base for writable integral UWB policy values."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    @property
    def native_value(self) -> int | None:
        """Return the configured value."""
        return self._value if isinstance(self._value, int) else None

    async def async_set_native_value(self, value: float) -> None:
        """Write an integral configuration value over Matter."""
        new_value = int(value)
        if isinstance(self, UwbDistanceNumber):
            self._validate_distance_order(new_value)
        await self._write_value(new_value)


class UwbDistanceNumber(UwbConfigNumber):
    """Base for distances that must remain in increasing order."""

    _distance_attribute_id: int

    def _validate_distance_order(self, new_value: int) -> None:
        """Reject a distance that breaks unlock < approach < relock."""
        node = self._matter.matter_client.get_node(self._node_id)
        values = {
            attribute_id: node.node_data.attributes.get(
                create_attribute_path(ENDPOINT_ID, CUSTOM_CLUSTER_ID, attribute_id)
            )
            for attribute_id in (
                UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID,
                APPROACH_CM_ATTRIBUTE_ID,
                RELOCK_CM_ATTRIBUTE_ID,
            )
        }
        values[self._distance_attribute_id] = new_value
        unlock = values[UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID]
        approach = values[APPROACH_CM_ATTRIBUTE_ID]
        relock = values[RELOCK_CM_ATTRIBUTE_ID]
        if not all(isinstance(item, int) for item in (unlock, approach, relock)):
            raise HomeAssistantError(
                "Cannot validate the distance: one or more current distance "
                "settings are unavailable"
            )
        if not unlock < approach < relock:
            raise HomeAssistantError(
                "Distances must satisfy unlock < approach < relock "
                f"(currently {unlock} < {approach} < {relock} cm)"
            )


class UwbUnlockDistanceNumber(UwbDistanceNumber):
    _attr_name = "Unlock distance"
    _distance_attribute_id = UNLOCK_THRESHOLD_CM_ATTRIBUTE_ID
    _attr_native_min_value = 20
    _attr_native_max_value = 999
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS


class UwbApproachDistanceNumber(UwbDistanceNumber):
    _attr_name = "Approach distance"
    _distance_attribute_id = APPROACH_CM_ATTRIBUTE_ID
    _attr_native_min_value = 21
    _attr_native_max_value = 999
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS


class UwbRelockDistanceNumber(UwbDistanceNumber):
    _attr_name = "Relock distance"
    _distance_attribute_id = RELOCK_CM_ATTRIBUTE_ID
    _attr_native_min_value = 22
    _attr_native_max_value = 1000
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS


class UwbMotorTimeNumber(UwbConfigNumber):
    _attr_name = "Motor time"
    _attr_native_min_value = 100
    _attr_native_max_value = 5000
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS


class UwbAutoRelockTimeNumber(UwbMatterEntity, NumberEntity):
    """Door Lock AutoRelockTime configuration."""

    _attr_name = "Auto-relock time"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 86400
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> int | None:
        """Return the configured auto-relock time."""
        return self._value if isinstance(self._value, int) else None

    async def async_set_native_value(self, value: float) -> None:
        """Set auto-relock time in seconds."""
        await self._write_value(int(value))
