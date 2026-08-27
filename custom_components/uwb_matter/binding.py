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
        snake_name = {
            "authMode": "auth_mode",
            "fabricIndex": "fabric_index",
        }.get(name)
        if snake_name is not None and snake_name in binding:
            return binding[snake_name]
        field_id = STRUCT_FIELD_IDS.get(name)
        if field_id is not None:
            return binding.get(str(field_id), binding.get(field_id))
        return None
    return getattr(binding, name, None)


def normalized_acl(value: object) -> list[dict[str, Any]]:
    """Convert cached ACL entries to Matter Server's write format."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        targets = field(item, "targets")
        normalized_targets = None
        if isinstance(targets, list):
            normalized_targets = []
            for target in targets:
                normalized_targets.append(
                    {
                        "cluster": _acl_target_field(target, "cluster", 0),
                        "endpoint": _acl_target_field(target, "endpoint", 1),
                        "device_type": _acl_target_field(
                            target, "deviceType", 2
                        ),
                    }
                )
        subjects = field(item, "subjects")
        normalized_subjects = None
        if isinstance(subjects, list):
            normalized_subjects = []
            for subject in subjects:
                normalized = _integer(subject)
                normalized_subjects.append(
                    normalized if normalized is not None else subject
                )
        result.append(
            {
                "privilege": _integer(field(item, "privilege")),
                "auth_mode": _integer(field(item, "authMode")),
                "subjects": normalized_subjects,
                "targets": normalized_targets,
            }
        )
    return result


def matter_server_acl_backup(value: object) -> list[dict[str, Any]]:
    """Convert ACL entries to Matter Server's paste-compatible JSON format."""
    if not isinstance(value, list):
        return []
    normalized = normalized_acl(value)
    result: list[dict[str, Any]] = []
    for source, entry in zip(value, normalized, strict=True):
        targets = entry["targets"]
        raw_targets = None
        if isinstance(targets, list):
            raw_targets = [
                {
                    "0": target["cluster"],
                    "1": target["endpoint"],
                    "2": target["device_type"],
                }
                for target in targets
            ]
        result.append(
            {
                "1": entry["privilege"],
                "2": entry["auth_mode"],
                "3": entry["subjects"],
                "4": raw_targets,
                "254": _integer(field(source, "fabricIndex")),
            }
        )
    return result


def _acl_target_field(target: object, name: str, field_id: int) -> int | None:
    """Read one nullable AccessControlTarget field."""
    if isinstance(target, dict):
        snake_name = "device_type" if name == "deviceType" else name
        value = target.get(
            name,
            target.get(
                snake_name, target.get(str(field_id), target.get(field_id))
            ),
        )
    else:
        value = getattr(target, name, None)
    return _integer(value)


def _integer(value: object) -> int | None:
    """Normalize an integer transported as either JSON number or string."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def normalized_bindings(value: object) -> list[dict[str, int | None]]:
    """Convert cached bindings to values accepted by Matter Server."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, int | None]] = []
    for item in value:
        target: dict[str, int | None] = {}
        for key in ("node", "group", "endpoint", "cluster"):
            target[key] = _integer(field(item, key))
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
