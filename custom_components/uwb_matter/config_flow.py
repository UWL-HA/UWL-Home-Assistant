"""Config flow for UltraWideLock Matter sensors."""

import json
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.components.matter.helpers import get_matter
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from matter_server.common.helpers.util import create_attribute_path
from matter_server.common.models import APICommand

from .binding import (
    binding_path,
    door_lock_bindings,
    matter_lock_name,
    matter_lock_targets,
    normalized_bindings,
    parse_target_key,
    target_key,
)
from .const import (
    CONF_CREDENTIAL_NAMES,
    CONF_CREDENTIAL_PRESENCE,
    CONF_STALE_TIMEOUT,
    CONF_WRITABLE_CONTROLS,
    CUSTOM_CLUSTER_ID,
    DEFAULT_STALE_TIMEOUT,
    DEVICE_IN_RANGE_ATTRIBUTE_ID,
    DOMAIN,
    DOOR_LOCK_CLUSTER_ID,
    ENDPOINT_ID,
)

CONF_CREDENTIAL_ID = "credential_id"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_CREATE_PRESENCE = "create_presence_sensor"
CONF_SETUP_CONFIRMED = "setup_confirmed"
CONF_SOURCE_LOCK = "source_lock"
CONF_TARGET_LOCK = "target_lock"
CONF_BINDING_TO_REMOVE = "binding_to_remove"
CONF_CONFIRM_BINDING_REMOVAL = "confirm_binding_removal"
CONF_MANUAL_ACL_CONFIRMED = "manual_acl_confirmed"


class UwbMatterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure UltraWideLock Matter sensors."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the credential naming options flow."""
        return UwbMatterOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose read-only or writable custom-cluster support."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._writable_controls = bool(
                user_input[CONF_WRITABLE_CONTROLS]
            )
            if self._writable_controls:
                return await self.async_step_writable_setup()
            return self.async_create_entry(
                title="UltraWideLock",
                data={CONF_WRITABLE_CONTROLS: False},
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_WRITABLE_CONTROLS, default=False): bool}
            ),
        )

    async def async_step_writable_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Guide installation of the optional Matter Server schema."""
        errors = {}
        if user_input is not None:
            if user_input[CONF_SETUP_CONFIRMED]:
                return self.async_create_entry(
                    title="UltraWideLock",
                    data={CONF_WRITABLE_CONTROLS: True},
                )
            errors[CONF_SETUP_CONFIRMED] = "setup_not_confirmed"
        return self.async_show_form(
            step_id="writable_setup",
            data_schema=vol.Schema(
                {vol.Required(CONF_SETUP_CONFIRMED, default=False): bool}
            ),
            errors=errors,
        )


class UwbMatterOptionsFlow(OptionsFlow):
    """Name automatically discovered UWB credentials."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer clearly separated data and credential settings."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["data_freshness", "credentials", "matter_binding"],
        )

    async def async_step_matter_binding(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the UltraWideLock whose bindings should be managed."""
        matter = get_matter(self.hass)
        registry = er.async_get(self.hass)
        presence_path = create_attribute_path(
            ENDPOINT_ID, CUSTOM_CLUSTER_ID, DEVICE_IN_RANGE_ATTRIBUTE_ID
        )
        sources = {
            str(node.node_id): matter_lock_name(
                self.hass, registry, node.node_id, ENDPOINT_ID, node.name
            )
            for node in matter.matter_client.get_nodes()
            if presence_path in node.node_data.attributes
        }
        if not sources:
            return self.async_abort(reason="no_ultrawidelocks")
        if user_input is not None:
            selected = user_input[CONF_SOURCE_LOCK]
            self._binding_source = int(selected)
            self._binding_source_name = sources[selected]
            return await self.async_step_binding_action()
        return self.async_show_form(
            step_id="matter_binding",
            data_schema=vol.Schema(
                {vol.Required(CONF_SOURCE_LOCK): vol.In(sources)}
            ),
        )

    async def async_step_binding_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose whether to add or remove a Door Lock binding."""
        return self.async_show_menu(
            step_id="binding_action",
            menu_options=["add_binding", "remove_binding"],
        )

    async def async_step_add_binding(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a standard binding without changing the target lock ACL."""
        matter = get_matter(self.hass)
        targets = matter_lock_targets(self.hass, matter)
        targets.pop(target_key(self._binding_source, ENDPOINT_ID), None)
        if not targets:
            return self.async_abort(reason="no_matter_locks")
        if user_input is not None:
            selected = user_input[CONF_TARGET_LOCK]
            target_node, target_endpoint = parse_target_key(selected)
            bindings = await self._current_bindings()
            candidate = {
                "node": target_node,
                "group": None,
                "endpoint": target_endpoint,
                "cluster": DOOR_LOCK_CLUSTER_ID,
            }
            if candidate not in bindings:
                try:
                    await self._write_bindings([*bindings, candidate])
                except Exception:  # noqa: BLE001
                    return self.async_abort(reason="binding_write_failed")
            self._manual_acl_target = (target_node, target_endpoint)
            self._manual_acl_target_name = targets[selected]
            return await self.async_step_manual_acl_add()
        return self.async_show_form(
            step_id="add_binding",
            data_schema=vol.Schema(
                {vol.Required(CONF_TARGET_LOCK): vol.In(targets)}
            ),
        )

    async def async_step_manual_acl_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain how to grant the binding permission in Matter Server."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_MANUAL_ACL_CONFIRMED]:
                return self.async_create_entry(
                    title="", data=self.config_entry.options
                )
            errors[CONF_MANUAL_ACL_CONFIRMED] = "manual_acl_not_confirmed"
        target_node, target_endpoint = self._manual_acl_target
        return self.async_show_form(
            step_id="manual_acl_add",
            data_schema=vol.Schema(
                {vol.Required(CONF_MANUAL_ACL_CONFIRMED, default=False): bool}
            ),
            errors=errors,
            description_placeholders={
                "source_lock": self._binding_source_name,
                "source_node": str(self._binding_source),
                "target_lock": self._manual_acl_target_name,
                "target_node": str(target_node),
                "target_endpoint": str(target_endpoint),
            },
        )

    async def async_step_remove_binding(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select one current Door Lock binding to remove."""
        registry = er.async_get(self.hass)
        choices = {
            target_key(item["node"], item["endpoint"]): matter_lock_name(
                self.hass, registry, item["node"], item["endpoint"]
            )
            for item in door_lock_bindings(self._cached_bindings())
            if item["node"] is not None and item["endpoint"] is not None
        }
        if not choices:
            return self.async_abort(reason="no_door_lock_bindings")
        if user_input is not None:
            selected = user_input[CONF_BINDING_TO_REMOVE]
            self._binding_to_remove = parse_target_key(selected)
            self._manual_acl_target_name = choices[selected]
            return await self.async_step_confirm_remove_binding()
        return self.async_show_form(
            step_id="remove_binding",
            data_schema=vol.Schema(
                {vol.Required(CONF_BINDING_TO_REMOVE): vol.In(choices)}
            ),
        )

    async def async_step_confirm_remove_binding(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the binding-table change before writing it."""
        node_id, endpoint = self._binding_to_remove
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_CONFIRM_BINDING_REMOVAL]:
                errors[CONF_CONFIRM_BINDING_REMOVAL] = (
                    "binding_removal_not_confirmed"
                )
            else:
                bindings = await self._current_bindings()
                updated = [
                    item
                    for item in bindings
                    if not (
                        item.get("node") == node_id
                        and item.get("endpoint") == endpoint
                        and item.get("cluster") == DOOR_LOCK_CLUSTER_ID
                    )
                ]
                if self._binding_signature(bindings) == self._binding_signature(
                    updated
                ):
                    return self.async_abort(reason="binding_not_found")
                try:
                    await self._write_bindings(updated)
                except Exception:  # noqa: BLE001
                    return self.async_abort(reason="binding_remove_failed")
                return await self.async_step_manual_acl_remove()
        return self.async_show_form(
            step_id="confirm_remove_binding",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONFIRM_BINDING_REMOVAL, default=False
                    ): bool
                }
            ),
            errors=errors,
            description_placeholders={
                "source_lock": self._binding_source_name,
                "target_lock": self._manual_acl_target_name,
            },
        )

    async def async_step_manual_acl_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain how to remove the stale permission in Matter Server."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_MANUAL_ACL_CONFIRMED]:
                return self.async_create_entry(
                    title="", data=self.config_entry.options
                )
            errors[CONF_MANUAL_ACL_CONFIRMED] = "manual_acl_not_confirmed"
        node_id, endpoint = self._binding_to_remove
        return self.async_show_form(
            step_id="manual_acl_remove",
            data_schema=vol.Schema(
                {vol.Required(CONF_MANUAL_ACL_CONFIRMED, default=False): bool}
            ),
            errors=errors,
            description_placeholders={
                "source_lock": self._binding_source_name,
                "source_node": str(self._binding_source),
                "target_lock": self._manual_acl_target_name,
                "target_node": str(node_id),
                "target_endpoint": str(endpoint),
            },
        )

    async def _current_bindings(self) -> list[dict[str, int | None]]:
        """Read the source node's complete current binding table."""
        path = binding_path(ENDPOINT_ID)
        client = get_matter(self.hass).matter_client
        values = await client.read_attribute(self._binding_source, path)
        value = values.get(path)
        node = client.get_node(self._binding_source)
        if callable(update := getattr(node, "update_attribute", None)):
            update(path, value)
        else:
            node.node_data.attributes[path] = value
        return normalized_bindings(value)

    def _cached_bindings(self) -> list[dict[str, int | None]]:
        """Return cached bindings without waiting on an unreachable node."""
        path = binding_path(ENDPOINT_ID)
        node = get_matter(self.hass).matter_client.get_node(self._binding_source)
        return normalized_bindings(node.node_data.attributes.get(path))

    async def _write_bindings(
        self, bindings: list[dict[str, int | None]]
    ) -> None:
        """Replace and verify the source node's standard binding table."""
        client = get_matter(self.hass).matter_client
        if callable(method := getattr(client, "set_node_binding", None)):
            result = await method(self._binding_source, ENDPOINT_ID, bindings)
        else:
            result = await client.send_command(
                APICommand.SET_NODE_BINDING,
                node_id=self._binding_source,
                endpoint=ENDPOINT_ID,
                bindings=bindings,
            )
        if isinstance(result, list):
            for item in result:
                status = (
                    item.get("status")
                    if isinstance(item, dict)
                    else getattr(item, "status", None)
                )
                if status not in (None, 0):
                    raise ValueError(
                        f"Matter binding write failed with status {status}"
                    )
        actual = await self._current_bindings()
        if self._binding_signature(actual) != self._binding_signature(bindings):
            raise ValueError("Matter binding verification failed")
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id),
            "reload UltraWideLock after binding change",
        )

    @staticmethod
    def _binding_signature(
        bindings: list[dict[str, int | None]],
    ) -> list[str]:
        """Return an order-independent signature for a binding table."""
        return sorted(json.dumps(entry, sort_keys=True) for entry in bindings)

    async def async_step_data_freshness(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure when live UWB subscription data becomes stale."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **user_input},
            )
        return self.async_show_form(
            step_id="data_freshness",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STALE_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_STALE_TIMEOUT, DEFAULT_STALE_TIMEOUT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=3, max=300))
                }
            ),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a discovered credential to name or disable."""
        credentials = dict(
            self.config_entry.options.get(CONF_CREDENTIAL_NAMES, {})
        )
        if user_input is not None:
            if not (credential_id := user_input.get(CONF_CREDENTIAL_ID)):
                return self.async_create_entry(
                    title="", data=self.config_entry.options
                )
            self._credential_id = credential_id
            return await self.async_step_credential()
        schema_fields: dict[vol.Marker, object] = {}
        if credentials:
            labels = {
                credential_id: (
                    f"{name} ({credential_id})" if name else credential_id
                )
                for credential_id, name in sorted(credentials.items())
            }
            schema_fields[vol.Required(CONF_CREDENTIAL_ID)] = vol.In(labels)
        schema = vol.Schema(schema_fields)
        return self.async_show_form(step_id="credentials", data_schema=schema)

    async def async_step_credential(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the name and occupancy entity for one credential."""
        credential_id = self._credential_id
        names = dict(self.config_entry.options.get(CONF_CREDENTIAL_NAMES, {}))
        presence = dict(
            self.config_entry.options.get(CONF_CREDENTIAL_PRESENCE, {})
        )
        if user_input is not None:
            names[credential_id] = str(user_input[CONF_FRIENDLY_NAME]).strip()
            enabled = bool(user_input[CONF_CREATE_PRESENCE])
            was_enabled = presence.get(credential_id, True)
            presence[credential_id] = enabled
            if was_enabled and not enabled:
                self._remove_presence_entities(credential_id)
            persistent_notification.async_dismiss(
                self.hass, f"uwb_matter_new_credential_{credential_id}"
            )
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_CREDENTIAL_NAMES: names,
                    CONF_CREDENTIAL_PRESENCE: presence,
                },
            )
        return self.async_show_form(
            step_id="credential",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FRIENDLY_NAME, default=names.get(credential_id, "")
                    ): str,
                    vol.Required(
                        CONF_CREATE_PRESENCE,
                        default=bool(presence.get(credential_id, True)),
                    ): bool,
                }
            ),
            description_placeholders={"credential_id": credential_id},
        )

    def _remove_presence_entities(self, credential_id: str) -> None:
        """Remove disabled credential-occupancy entities from the registry."""
        registry = er.async_get(self.hass)
        suffix = f"-credential-presence-{credential_id}"
        for entity in er.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        ):
            if entity.unique_id.endswith(suffix):
                registry.async_remove(entity.entity_id)
