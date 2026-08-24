"""Switch controls for UltraWideLock Matter devices."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BOUND_UNLOCK_ATTRIBUTE_ID,
    CUSTOM_CLUSTER_ID,
    DISTANCE_RELOCK_ATTRIBUTE_ID,
    ULTRAWIDELOCK_RELOCK_ATTRIBUTE_ID,
    ULTRAWIDELOCK_UNLOCK_ATTRIBUTE_ID,
)
from .entity import UwbMatterEntity, async_setup_uwb_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UltraWideLock switches."""
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        (
            (CUSTOM_CLUSTER_ID, DISTANCE_RELOCK_ATTRIBUTE_ID),
            (CUSTOM_CLUSTER_ID, BOUND_UNLOCK_ATTRIBUTE_ID),
            (CUSTOM_CLUSTER_ID, ULTRAWIDELOCK_RELOCK_ATTRIBUTE_ID),
            (CUSTOM_CLUSTER_ID, ULTRAWIDELOCK_UNLOCK_ATTRIBUTE_ID),
        ),
        _uwb_policy_switch_factory,
    )


def _uwb_policy_switch_factory(
    hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
) -> UwbMatterEntity:
    """Create a writable UWB action-policy switch."""
    entity_class = {
        DISTANCE_RELOCK_ATTRIBUTE_ID: UwbBoundRelockSwitch,
        BOUND_UNLOCK_ATTRIBUTE_ID: UwbBoundUnlockSwitch,
        ULTRAWIDELOCK_RELOCK_ATTRIBUTE_ID: UwbLockRelockSwitch,
        ULTRAWIDELOCK_UNLOCK_ATTRIBUTE_ID: UwbLockUnlockSwitch,
    }[attribute_id]
    return entity_class(hass, node_id, cluster_id, attribute_id)


class UwbPolicySwitch(UwbMatterEntity, SwitchEntity):
    """Base for persistent UWB action-policy switches."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        """Return whether this action is enabled."""
        return None if self._value is None else bool(self._value)

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable this action."""
        await self._write_value(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable this action."""
        await self._write_value(False)


class UwbBoundRelockSwitch(UwbPolicySwitch):
    _attr_name = "Lock action · Bound relock"


class UwbBoundUnlockSwitch(UwbPolicySwitch):
    _attr_name = "Lock action · Bound unlock"


class UwbLockRelockSwitch(UwbPolicySwitch):
    _attr_name = "Lock action · UWL relock"


class UwbLockUnlockSwitch(UwbPolicySwitch):
    _attr_name = "Lock action · UWL unlock"
