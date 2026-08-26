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
