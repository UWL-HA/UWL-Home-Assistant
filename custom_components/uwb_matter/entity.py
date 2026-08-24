"""Entity support for UltraWideLock Matter devices."""

from collections.abc import Callable
from typing import Any

from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import EventType

from homeassistant.components.matter.const import (
    DOMAIN as MATTER_DOMAIN,
    ID_TYPE_DEVICE_ID,
)
from homeassistant.components.matter.helpers import get_matter
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CUSTOM_CLUSTER_ID,
    DEVICE_IN_RANGE_ATTRIBUTE_ID,
    DOMAIN,
    ENDPOINT_ID,
)

AttributeTarget = tuple[int, int]
EntityFactory = Callable[[HomeAssistant, int, int, int], "UwbMatterEntity"]


class UwbMatterEntity(Entity):
    """Base for an entity backed by a raw Matter attribute."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, hass: HomeAssistant, node_id: int, cluster_id: int, attribute_id: int
    ) -> None:
        """Initialize the entity."""
        self._matter = get_matter(hass)
        self._hass = hass
        self._config_entry: ConfigEntry | None = None
        self._node_id = node_id
        self._attribute_path = create_attribute_path(
            ENDPOINT_ID, cluster_id, attribute_id
        )
        server_info = self._matter.matter_client.server_info
        assert server_info is not None
        node = self._matter.matter_client.get_node(node_id)
        basic_info = node.device_info
        operational_id = f"{server_info.compressed_fabric_id:016X}-{node_id:016X}"
        matter_device_id = f"{operational_id}-MatterNodeDevice"
        matter_device = dr.async_get(hass).async_get_device(
            identifiers={(MATTER_DOMAIN, f"{ID_TYPE_DEVICE_ID}_{matter_device_id}")}
        )
        device_name = (
            matter_device.name_by_user
            if matter_device is not None and matter_device.name_by_user
            else matter_device.name
            if matter_device is not None and matter_device.name
            else node.name or basic_info.productName or "UltraWideLock"
        )
        self._attr_unique_id = (
            f"deviceid_{matter_device_id}-"
            f"{ENDPOINT_ID}-{cluster_id}-{attribute_id}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, operational_id)},
            name=device_name,
            manufacturer=basic_info.vendorName,
            model=basic_info.productName,
            serial_number=basic_info.serialNumber,
        )
        self._value = self._read_value()

    def _read_value(self) -> Any:
        """Read an attribute value from the Matter node's raw cache."""
        node = self._matter.matter_client.get_node(self._node_id)
        return node.node_data.attributes.get(self._attribute_path)

    async def _write_value(self, value: Any) -> None:
        """Write the entity's Matter attribute."""
        await self._matter.matter_client.write_attribute(
            self._node_id, self._attribute_path, value
        )

    @property
    def available(self) -> bool:
        """Return whether the Matter node is available."""
        return self._matter.matter_client.get_node(self._node_id).available

    async def async_added_to_hass(self) -> None:
        """Subscribe to Matter updates."""
        self.async_on_remove(
            self._matter.matter_client.subscribe_events(
                callback=self._attribute_updated,
                event_filter=EventType.ATTRIBUTE_UPDATED,
                node_filter=self._node_id,
                attr_path_filter=self._attribute_path,
            )
        )
        self.async_on_remove(
            self._matter.matter_client.subscribe_events(
                callback=self._node_updated,
                event_filter=EventType.NODE_UPDATED,
                node_filter=self._node_id,
            )
        )

    def _attribute_updated(self, event: EventType, data: Any) -> None:
        """Handle a pushed attribute value."""
        self._value = data
        self.schedule_update_ha_state()

    def _node_updated(self, event: EventType, data: Any) -> None:
        """Handle node availability and refreshed values."""
        self._value = self._read_value()
        self.schedule_update_ha_state()


def async_setup_uwb_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    targets: tuple[AttributeTarget, ...],
    entity_factory: EntityFactory,
) -> None:
    """Add entities for existing and newly discovered UltraWideLock nodes."""
    matter = get_matter(hass)
    seen: set[tuple[int, int, int]] = set()
    presence_path = create_attribute_path(
        ENDPOINT_ID, CUSTOM_CLUSTER_ID, DEVICE_IN_RANGE_ATTRIBUTE_ID
    )

    def add_node(node_id: int) -> None:
        node = matter.matter_client.get_node(node_id)
        if presence_path not in node.node_data.attributes:
            return
        entities = []
        for cluster_id, attribute_id in targets:
            key = (node_id, cluster_id, attribute_id)
            path = create_attribute_path(ENDPOINT_ID, cluster_id, attribute_id)
            custom_cluster_target = cluster_id == CUSTOM_CLUSTER_ID
            if key not in seen and (
                custom_cluster_target or path in node.node_data.attributes
            ):
                seen.add(key)
                entity = entity_factory(hass, node_id, cluster_id, attribute_id)
                entity._config_entry = entry
                entities.append(entity)
        if entities:
            async_add_entities(entities)

    for node in matter.matter_client.get_nodes():
        add_node(node.node_id)

    def node_discovered(event: EventType, node: Any) -> None:
        """Add entities when a node is added or re-interviewed."""
        add_node(node.node_id)

    for event_type in (EventType.NODE_ADDED, EventType.NODE_UPDATED):
        entry.async_on_unload(
            matter.matter_client.subscribe_events(
                callback=node_discovered, event_filter=event_type
            )
        )
