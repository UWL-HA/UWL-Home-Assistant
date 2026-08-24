"""UltraWideLock Matter sensors integration."""

from pathlib import Path

from matter_server.common.models import EventType

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.matter.helpers import get_matter
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import CONF_CREDENTIAL_NAMES, DOMAIN, PLATFORMS
from .history import UwbHistoryStore

CARD_URL = "/uwb_matter/uwb-approach-card.js"
CARD_RESOURCE_URL = f"{CARD_URL}?v=0.13.3"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Serve and load the bundled dashboard card."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_URL,
                str(Path(__file__).parent / "www" / "uwb-approach-card.js"),
                True,
            )
        ]
    )
    lovelace = hass.data[LOVELACE_DATA]
    if lovelace.resource_mode == MODE_STORAGE:
        resources = lovelace.resources
        await resources.async_get_info()
        existing = next(
            (
                item
                for item in resources.async_items()
                if item[CONF_URL].split("?", 1)[0] == CARD_URL
            ),
            None,
        )
        if existing is None:
            await resources.async_create_item(
                {"res_type": "module", CONF_URL: CARD_RESOURCE_URL}
            )
        elif existing[CONF_URL] != CARD_RESOURCE_URL:
            await resources.async_update_item(
                existing[CONF_ID],
                {"res_type": "module", CONF_URL: CARD_RESOURCE_URL},
            )
    else:
        add_extra_js_url(hass, CARD_RESOURCE_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UltraWideLock Matter sensors from a config entry."""
    history = UwbHistoryStore(hass)
    await history.async_load()
    history.credential_names = dict(
        entry.options.get(CONF_CREDENTIAL_NAMES, {})
    )
    hass.data[DOMAIN] = history
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    matter = get_matter(hass)
    server_info = matter.matter_client.server_info
    assert server_info is not None
    fabric_id = server_info.compressed_fabric_id

    def remove_companion_device(operational_id: str) -> None:
        """Remove one UltraWideLock companion device and all its entities."""
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, operational_id)}
        )
        if device is None:
            return
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_device(entity_registry, device.id):
            entity_registry.async_remove(entity.entity_id)
        device_registry.async_remove_device(device.id)

    current_operational_ids = {
        f"{fabric_id:016X}-{node.node_id:016X}"
        for node in matter.matter_client.get_nodes()
    }
    device_registry = dr.async_get(hass)
    for device in list(device_registry.devices.values()):
        for device_identifier in device.identifiers:
            if (
                len(device_identifier) == 2
                and device_identifier[0] == DOMAIN
                and device_identifier[1] not in current_operational_ids
            ):
                remove_companion_device(device_identifier[1])
                break

    def node_removed(_event: EventType, node: object) -> None:
        """Remove the companion device after its native Matter node is removed."""
        node_id = node if isinstance(node, int) else getattr(node, "node_id", None)
        if node_id is None:
            return
        operational_id = f"{fabric_id:016X}-{node_id:016X}"
        remove_companion_device(operational_id)

    entry.async_on_unload(
        matter.matter_client.subscribe_events(
            callback=node_removed, event_filter=EventType.NODE_REMOVED
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an UltraWideLock Matter sensors config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload only when a friendly credential name changes."""
    history: UwbHistoryStore | None = hass.data.get(DOMAIN)
    if history is not None:
        old_named = {
            key: value for key, value in history.credential_names.items() if value
        }
        new_names = dict(entry.options.get(CONF_CREDENTIAL_NAMES, {}))
        new_named = {key: value for key, value in new_names.items() if value}
        history.credential_names = new_names
        if old_named == new_named:
            return
    await hass.config_entries.async_reload(entry.entry_id)
