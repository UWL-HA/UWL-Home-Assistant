"""Lock control for UltraWideLock Matter devices."""

from typing import Any

from chip.clusters import Objects as clusters

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOOR_LOCK_CLUSTER_ID, ENDPOINT_ID, LOCK_STATE_ATTRIBUTE_ID
from .entity import UwbMatterEntity, async_setup_uwb_entities

TIMED_REQUEST_TIMEOUT_MS = 1000


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UltraWideLock lock controls."""
    async_setup_uwb_entities(
        hass,
        entry,
        async_add_entities,
        ((DOOR_LOCK_CLUSTER_ID, LOCK_STATE_ATTRIBUTE_ID),),
        UwbLock,
    )


class UwbLock(UwbMatterEntity, LockEntity):
    """UltraWideLock lock control."""

    _attr_name = None

    @property
    def is_locked(self) -> bool | None:
        """Return whether the lock is locked."""
        if not isinstance(self._value, int):
            return None
        return self._value == 1

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door."""
        await self._matter.matter_client.send_device_command(
            self._node_id,
            ENDPOINT_ID,
            clusters.DoorLock.Commands.LockDoor(None),
            timed_request_timeout_ms=TIMED_REQUEST_TIMEOUT_MS,
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self._matter.matter_client.send_device_command(
            self._node_id,
            ENDPOINT_ID,
            clusters.DoorLock.Commands.UnlockDoor(None),
            timed_request_timeout_ms=TIMED_REQUEST_TIMEOUT_MS,
        )
