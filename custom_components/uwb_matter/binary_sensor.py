"""Binary sensors for UltraWideLock Matter devices."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ACTUATOR_ENABLED_ATTRIBUTE_ID,
    CUSTOM_CLUSTER_ID,
    DEVICE_IN_RANGE_ATTRIBUTE_ID,
    DOOR_LOCK_CLUSTER_ID,
)
from .entity import UwbMatterEntity, async_setup_uwb_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UltraWideLock binary sensors."""
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        (
            (CUSTOM_CLUSTER_ID, DEVICE_IN_RANGE_ATTRIBUTE_ID),
            (DOOR_LOCK_CLUSTER_ID, ACTUATOR_ENABLED_ATTRIBUTE_ID),
        ),
        _binary_sensor_factory,
    )


def _binary_sensor_factory(
    hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
) -> UwbMatterEntity:
    """Create the entity belonging to a binary attribute."""
    entity_class = (
        UwbDeviceInRangeBinarySensor
        if cluster_id == CUSTOM_CLUSTER_ID
        else UwbActuatorBinarySensor
    )
    return entity_class(hass, node_id, cluster_id, attribute_id)


class UwbDeviceInRangeBinarySensor(UwbMatterEntity, BinarySensorEntity):
    """Whether an authenticated UWB device is currently in range."""

    _attr_name = "UWB device in range"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @property
    def is_on(self) -> bool | None:
        """Return whether a UWB device is in range."""
        return None if self._value is None else bool(self._value)


class UwbActuatorBinarySensor(UwbMatterEntity, BinarySensorEntity):
    """Whether the lock actuator is enabled."""

    _attr_name = "Actuator"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        """Return whether the actuator is enabled."""
        return None if self._value is None else bool(self._value)
