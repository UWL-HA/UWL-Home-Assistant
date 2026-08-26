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
    normalized_acl,
    normalized_bindings,
    parse_target_key,
    target_key,
)
from .const import (
    ACCESS_CONTROL_CLUSTER_ID,
    ACL_ATTRIBUTE_ID,
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
CONF_CONFIRM_ACL_RISK = "confirm_acl_risk"
CONF_ACL_BACKUP_SAVED = "acl_backup_saved"


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
            self._binding_source = int(user_input[CONF_SOURCE_LOCK])
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
        """Add one standard Matter Door Lock binding."""
        matter = get_matter(self.hass)
        targets = matter_lock_targets(self.hass, matter)
        targets.pop(target_key(self._binding_source, ENDPOINT_ID), None)
        if not targets:
            return self.async_abort(reason="no_matter_locks")
        errors: dict[str, str] = {}
        if user_input is not None:
            target_node, target_endpoint = parse_target_key(
                user_input[CONF_TARGET_LOCK]
            )
            try:
                acl = await self._current_acl(target_node)
            except Exception:  # noqa: BLE001
                return self.async_abort(reason="acl_read_failed")
            if not self._target_acl_allows(
                acl, self._binding_source, target_endpoint
            ):
                self._acl_target = (target_node, target_endpoint)
                self._acl_backup = acl
                return await self.async_step_confirm_acl()
            return await self._finish_add_binding(target_node, target_endpoint)
        return self.async_show_form(
            step_id="add_binding",
            data_schema=vol.Schema(
                {vol.Required(CONF_TARGET_LOCK): vol.In(targets)}
            ),
            errors=errors,
        )

    async def async_step_confirm_acl(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Warn before granting the UltraWideLock access to a target lock."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_ACL_BACKUP_SAVED]:
                errors[CONF_ACL_BACKUP_SAVED] = "acl_backup_not_saved"
            elif not user_input[CONF_CONFIRM_ACL_RISK]:
                errors[CONF_CONFIRM_ACL_RISK] = "acl_risk_not_confirmed"
            else:
                target_node, target_endpoint = self._acl_target
                try:
                    current_acl = await self._current_acl(target_node)
                except Exception:  # noqa: BLE001
                    return self.async_abort(reason="acl_read_failed")
                if self._acl_signature(current_acl) != self._acl_signature(
                    self._acl_backup
                ):
                    return self.async_abort(reason="acl_changed")
                updated_acl = [
                    *self._acl_backup,
                    {
                        "privilege": 3,
                        "auth_mode": 2,
                        "subjects": [self._binding_source],
                        "targets": [
                            {
                                "cluster": DOOR_LOCK_CLUSTER_ID,
                                "endpoint": target_endpoint,
                                "device_type": None,
                            }
                        ],
                    },
                ]
                self._create_acl_recovery_notification(
                    target_node, self._acl_backup
                )
                try:
                    await self._write_acl(target_node, updated_acl)
                except Exception:  # noqa: BLE001
                    try:
                        await self._write_acl(target_node, self._acl_backup)
                    except Exception:  # noqa: BLE001
                        return self.async_abort(reason="acl_rollback_failed")
                    errors["base"] = "acl_write_failed"
                if not errors:
                    result = await self._finish_add_binding(
                        target_node, target_endpoint, self._acl_backup
                    )
                    return result
        return self.async_show_form(
            step_id="confirm_acl",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACL_BACKUP_SAVED, default=False): bool,
                    vol.Required(CONF_CONFIRM_ACL_RISK, default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "target_node": str(self._acl_target[0]),
                "acl_backup": json.dumps(self._acl_backup, indent=2),
            },
        )

    def _create_acl_recovery_notification(
        self, target_node: int, acl: list[dict[str, Any]]
    ) -> None:
        """Persist the pre-write ACL and recovery guidance outside the flow."""
        persistent_notification.async_create(
            self.hass,
            "The UltraWideLock integration is about to change this lock's "
            "Matter ACL. Keep this original ACL until the binding has been "
            "tested:\n\n```json\n"
            f"{json.dumps(acl, indent=2)}"
            "\n```\n\nIf access is lost, restore this complete ACL through another "
            "Matter administrator on the same fabric. If no administrator "
            "can reach the lock, factory-reset the lock and commission it "
            "again as a last resort.",
            title=f"Matter ACL backup for node {target_node}",
            notification_id=f"uwb_matter_acl_backup_{target_node}",
        )

    async def _finish_add_binding(
        self,
        target_node: int,
        target_endpoint: int,
        acl_rollback: list[dict[str, Any]] | None = None,
    ) -> ConfigFlowResult:
        """Write and verify one Door Lock binding."""
        bindings = await self._current_bindings()
        candidate = {
            "node": target_node,
            "group": None,
            "endpoint": target_endpoint,
            "cluster": DOOR_LOCK_CLUSTER_ID,
        }
        if candidate not in bindings:
            bindings.append(candidate)
            try:
                await self._write_bindings(bindings)
            except Exception:  # noqa: BLE001
                if acl_rollback is not None:
                    try:
                        await self._write_acl(target_node, acl_rollback)
                    except Exception:  # noqa: BLE001
                        return self.async_abort(reason="acl_rollback_failed")
                return self.async_abort(reason="binding_write_failed")
        return self.async_create_entry(title="", data=self.config_entry.options)

    async def async_step_remove_binding(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one Door Lock binding while preserving all other entries."""
        registry = er.async_get(self.hass)
        current = await self._current_bindings()
        locks = door_lock_bindings(current)
        choices = {
            target_key(item["node"], item["endpoint"]): matter_lock_name(
                self.hass, registry, item["node"], item["endpoint"]
            )
            for item in locks
        }
        if not choices:
            return self.async_abort(reason="no_door_lock_bindings")
        errors: dict[str, str] = {}
        if user_input is not None:
            node_id, endpoint = parse_target_key(
                user_input[CONF_BINDING_TO_REMOVE]
            )
            updated = [
                item
                for item in current
                if not (
                    item.get("node") == node_id
                    and item.get("endpoint") == endpoint
                    and item.get("cluster") == DOOR_LOCK_CLUSTER_ID
                )
            ]
            try:
                await self._write_bindings(updated)
            except Exception:  # noqa: BLE001
                errors["base"] = "binding_write_failed"
            if not errors:
                return self.async_create_entry(
                    title="", data=self.config_entry.options
                )
        return self.async_show_form(
            step_id="remove_binding",
            data_schema=vol.Schema(
                {vol.Required(CONF_BINDING_TO_REMOVE): vol.In(choices)}
            ),
            errors=errors,
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

    async def _write_bindings(
        self, bindings: list[dict[str, int | None]]
    ) -> None:
        """Replace the source binding table through Matter Server's safe API."""
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
        path = binding_path(ENDPOINT_ID)
        client.get_node(self._binding_source).node_data.attributes[path] = bindings
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id),
            "reload UltraWideLock after binding change",
        )

    async def _current_acl(self, target_node: int) -> list[dict[str, Any]]:
        """Read the current fabric's ACL directly from the target lock."""
        path = create_attribute_path(0, ACCESS_CONTROL_CLUSTER_ID, ACL_ATTRIBUTE_ID)
        values = await get_matter(self.hass).matter_client.send_command(
            APICommand.READ_ATTRIBUTE,
            node_id=target_node,
            attribute_path=path,
            fabric_filtered=True,
        )
        acl = normalized_acl(values.get(path))
        if not acl or not any(
            entry.get("privilege") == 5
            and entry.get("auth_mode") == 2
            and entry.get("subjects")
            for entry in acl
        ):
            raise ValueError("ACL has no visible CASE administrator entry")
        return acl

    async def _write_acl(
        self, target_node: int, acl: list[dict[str, Any]]
    ) -> None:
        """Replace this fabric's ACL and validate the Matter write status."""
        client = get_matter(self.hass).matter_client
        if callable(method := getattr(client, "set_acl_entry", None)):
            result = await method(target_node, acl)
        else:
            result = await client.send_command(
                APICommand.SET_ACL_ENTRY, node_id=target_node, entry=acl
            )
        if isinstance(result, list):
            for item in result:
                status = (
                    item.get("status")
                    if isinstance(item, dict)
                    else getattr(item, "status", None)
                )
                if status not in (None, 0):
                    raise ValueError(f"Matter ACL write failed with status {status}")
        actual = self._acl_signature(await self._current_acl(target_node))
        if actual != self._acl_signature(acl):
            raise ValueError(
                "Matter ACL verification did not match the requested table"
            )

    @staticmethod
    def _acl_signature(acl: list[dict[str, Any]]) -> list[str]:
        """Return an order-independent, exact signature for an ACL table."""
        return sorted(json.dumps(entry, sort_keys=True) for entry in acl)

    def _target_acl_allows(
        self, acl: list[dict[str, Any]], source_node: int, endpoint: int
    ) -> bool:
        """Return whether the target ACL grants CASE Operate or higher."""
        for entry in acl:
            subjects = entry["subjects"]
            privilege = entry["privilege"]
            auth_mode = entry["auth_mode"]
            targets = entry["targets"]
            if (
                isinstance(subjects, list)
                and source_node in subjects
                and isinstance(privilege, int)
                and privilege >= 3
                and auth_mode == 2
                and (
                    targets is None
                    or any(
                        (target["cluster"] in (None, DOOR_LOCK_CLUSTER_ID))
                        and target["endpoint"] in (None, endpoint)
                        for target in targets
                    )
                )
            ):
                return True
        return False

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
