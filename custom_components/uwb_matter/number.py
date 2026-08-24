"""Number controls for UltraWideLock Matter devices."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    APPROACH_CM_ATTRIBUTE_ID,
    AUTO_RELOCK_TIME_ATTRIBUTE_ID,
    CUSTOM_CLUSTER_ID,
    DOOR_LOCK_CLUSTER_ID,
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
        await self._write_value(int(value))


class UwbUnlockDistanceNumber(UwbConfigNumber):
    _attr_name = "Unlock distance"
    _attr_native_min_value = 20
    _attr_native_max_value = 999
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS


class UwbApproachDistanceNumber(UwbConfigNumber):
    _attr_name = "Approach distance"
    _attr_native_min_value = 21
    _attr_native_max_value = 999
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS


class UwbRelockDistanceNumber(UwbConfigNumber):
    _attr_name = "Relock distance"
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
