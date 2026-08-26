"""Config flow for UltraWideLock Matter sensors."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CREDENTIAL_NAMES,
    CONF_CREDENTIAL_PRESENCE,
    CONF_STALE_TIMEOUT,
    CONF_WRITABLE_CONTROLS,
    DEFAULT_STALE_TIMEOUT,
    DOMAIN,
)

CONF_CREDENTIAL_ID = "credential_id"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_CREATE_PRESENCE = "create_presence_sensor"
CONF_SETUP_CONFIRMED = "setup_confirmed"


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
            menu_options=["data_freshness", "credentials"],
        )

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
