"""Helpers for standard Matter Door Lock bindings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.matter.const import DOMAIN as MATTER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from matter_server.common.helpers.util import create_attribute_path

from .const import (
    BINDING_ATTRIBUTE_ID,
    BINDING_CLUSTER_ID,
    DOOR_LOCK_CLUSTER_ID,
    ENDPOINT_ID,
)


def binding_path(endpoint: int = ENDPOINT_ID) -> str:
    """Return the standard Matter Binding attribute path."""
    return create_attribute_path(endpoint, BINDING_CLUSTER_ID, BINDING_ATTRIBUTE_ID)

STRUCT_FIELD_IDS = {
    "node": 1,
    "group": 2,
    "endpoint": 3,
    "cluster": 4,
    "fabricIndex": 254,
    "privilege": 1,
    "authMode": 2,
    "subjects": 3,
    "targets": 4,
}


def field(binding: object, name: str) -> Any:
    """Read a binding field from either JSON or an SDK struct."""
    if isinstance(binding, dict):
        if name in binding:
            return binding[name]
        field_id = STRUCT_FIELD_IDS.get(name)
        if field_id is not None:
            return binding.get(str(field_id), binding.get(field_id))
        return None
    return getattr(binding, name, None)


def normalized_bindings(value: object) -> list[dict[str, int | None]]:
    """Convert cached bindings to values accepted by Matter Server."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, int | None]] = []
    for item in value:
        target: dict[str, int | None] = {}
        for key in ("node", "group", "endpoint", "cluster"):
            item_value = field(item, key)
            target[key] = item_value if isinstance(item_value, int) else None
        if target["node"] is not None or target["group"] is not None:
            result.append(target)
    return result


def door_lock_bindings(value: object) -> list[dict[str, int | None]]:
    """Return unicast Door Lock targets only."""
    return [
        item
        for item in normalized_bindings(value)
        if item.get("cluster") == DOOR_LOCK_CLUSTER_ID
        and "node" in item
        and "endpoint" in item
    ]


def target_key(node_id: int, endpoint: int) -> str:
    """Create a stable UI key for a target endpoint."""
    return f"{node_id}:{endpoint}"


def parse_target_key(value: str) -> tuple[int, int]:
    """Parse a target key from the options flow."""
    node_id, endpoint = value.split(":", 1)
    return int(node_id), int(endpoint)


def matter_lock_targets(hass: HomeAssistant, matter: Any) -> dict[str, str]:
    """Return Matter Door Lock endpoints with friendly Home Assistant names."""
    registry = er.async_get(hass)
    targets: dict[str, str] = {}
    for node in matter.matter_client.get_nodes():
        for path in node.node_data.attributes:
            parts = path.split("/")
            if len(parts) != 3:
                continue
            try:
                endpoint, cluster, attribute = map(int, parts)
            except ValueError:
                continue
            if cluster != DOOR_LOCK_CLUSTER_ID or attribute != 0:
                continue
            key = target_key(node.node_id, endpoint)
            targets[key] = matter_lock_name(
                hass, registry, node.node_id, endpoint, node.name
            )
    return targets


def matter_lock_name(
    hass: HomeAssistant,
    registry: er.EntityRegistry,
    node_id: int,
    endpoint: int,
    fallback: str | None = None,
) -> str:
    """Resolve a Matter lock endpoint to its Home Assistant friendly name."""
    return matter_lock_info(hass, registry, node_id, endpoint, fallback)["name"]


def matter_lock_info(
    hass: HomeAssistant,
    registry: er.EntityRegistry,
    node_id: int,
    endpoint: int,
    fallback: str | None = None,
) -> dict[str, str | int | None]:
    """Resolve identifying details for one Matter lock endpoint."""
    needle = f"-{node_id:016X}-MatterNodeDevice-{endpoint}-"
    for entity in registry.entities.values():
        if (
            entity.platform == MATTER_DOMAIN
            and entity.domain == "lock"
            and needle in entity.unique_id
        ):
            state = hass.states.get(entity.entity_id)
            return {
                "name": entity.name
                or (state.name if state else None)
                or entity.entity_id,
                "entity_id": entity.entity_id,
                "node": node_id,
                "endpoint": endpoint,
                "cluster": "Door Lock (0x0101)",
            }
    return {
        "name": fallback or f"Matter node {node_id}, endpoint {endpoint}",
        "entity_id": None,
        "node": node_id,
        "endpoint": endpoint,
        "cluster": "Door Lock (0x0101)",
    }
