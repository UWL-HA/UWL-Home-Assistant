"""Helpers for standard Matter Door Lock bindings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.matter.const import DOMAIN as MATTER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOOR_LOCK_CLUSTER_ID


def field(binding: object, name: str) -> Any:
    """Read a binding field from either JSON or an SDK struct."""
    if isinstance(binding, dict):
        return binding.get(name, binding.get(f"{name[0].lower()}{name[1:]}"))
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
    needle = f"-{node_id:016X}-MatterNodeDevice-{endpoint}-"
    for entity in registry.entities.values():
        if (
            entity.platform == MATTER_DOMAIN
            and entity.domain == "lock"
            and needle in entity.unique_id
        ):
            state = hass.states.get(entity.entity_id)
            return entity.name or (state.name if state else None) or entity.entity_id
    return fallback or f"Matter node {node_id}, endpoint {endpoint}"
