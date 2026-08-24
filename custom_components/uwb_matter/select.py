"""Select controls for UltraWideLock Matter devices."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOOR_LOCK_CLUSTER_ID, OPERATING_MODE_ATTRIBUTE_ID
from .entity import UwbMatterEntity, async_setup_uwb_entities

OPERATING_MODES = {
    "Normal": 0,
    "No remote lock/unlock": 3,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UltraWideLock select controls."""
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((DOOR_LOCK_CLUSTER_ID, OPERATING_MODE_ATTRIBUTE_ID),),
        UwbOperatingModeSelect,
    )


class UwbOperatingModeSelect(UwbMatterEntity, SelectEntity):
    """Door Lock OperatingMode configuration."""

    _attr_name = "Operating mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(OPERATING_MODES)

    @property
    def current_option(self) -> str | None:
        """Return the current operating mode."""
        if not isinstance(self._value, int):
            return None
        return next(
            (name for name, value in OPERATING_MODES.items() if value == self._value),
            None,
        )

    async def async_select_option(self, option: str) -> None:
        """Set the operating mode."""
        await self._write_value(OPERATING_MODES[option])
