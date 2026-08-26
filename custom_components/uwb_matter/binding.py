"""Helpers for standard Matter Door Lock bindings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.matter.const import DOMAIN as MATTER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOOR_LOCK_CLUSTER_ID

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


def normalized_bindings(value: object) -> list[dict[str, int]]:
    """Convert cached bindings to values accepted by Matter Server."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, int]] = []
    for item in value:
        target = {
            key: item_value
            for key in ("node", "group", "endpoint", "cluster")
            if isinstance((item_value := field(item, key)), int)
        }
        if target:
            result.append(target)
    return result


def door_lock_bindings(value: object) -> list[dict[str, int]]:
    """Return unicast Door Lock targets only."""
    return [
        item
        for item in normalized_bindings(value)
        if item.get("cluster") == DOOR_LOCK_CLUSTER_ID
        and "node" in item
        and "endpoint" in item
    ]


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
