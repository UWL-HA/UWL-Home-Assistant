"""Config flow for UltraWideLock Matter sensors."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CREDENTIAL_NAMES,
    CONF_CREDENTIAL_PRESENCE,
    CONF_STALE_TIMEOUT,
    DEFAULT_STALE_TIMEOUT,
    DOMAIN,
)

PRESENCE_PREFIX = "presence__"


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
        """Create the single integration entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="UltraWideLock", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))


class UwbMatterOptionsFlow(OptionsFlow):
    """Name automatically discovered UWB credentials."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show naming and optional presence sensor controls."""
        credentials = dict(
            self.config_entry.options.get(CONF_CREDENTIAL_NAMES, {})
        )
        presence = dict(
            self.config_entry.options.get(CONF_CREDENTIAL_PRESENCE, {})
        )
        if user_input is not None:
            names = {
                credential_id: str(user_input.get(credential_id, "")).strip()
                for credential_id in credentials
            }
            enabled_presence = {
                credential_id: bool(
                    user_input.get(f"{PRESENCE_PREFIX}{credential_id}", False)
                )
                for credential_id in credentials
            }
            disabled = {
                credential_id
                for credential_id, was_enabled in presence.items()
                if was_enabled and not enabled_presence.get(credential_id, False)
            }
            if disabled:
                registry = er.async_get(self.hass)
                suffixes = tuple(
                    f"-credential-presence-{credential_id}"
                    for credential_id in disabled
                )
                for entity in er.async_entries_for_config_entry(
                    registry, self.config_entry.entry_id
                ):
                    if entity.unique_id.endswith(suffixes):
                        registry.async_remove(entity.entity_id)
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_CREDENTIAL_NAMES: names,
                    CONF_CREDENTIAL_PRESENCE: enabled_presence,
                    CONF_STALE_TIMEOUT: user_input[CONF_STALE_TIMEOUT],
                },
            )

        schema_fields: dict[vol.Marker, object] = {
            vol.Required(
                CONF_STALE_TIMEOUT,
                default=self.config_entry.options.get(
                    CONF_STALE_TIMEOUT, DEFAULT_STALE_TIMEOUT
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=3, max=300))
        }
        for credential_id, name in sorted(credentials.items()):
            schema_fields[vol.Optional(credential_id, default=name)] = str
            schema_fields[
                vol.Optional(
                    f"{PRESENCE_PREFIX}{credential_id}",
                    default=bool(presence.get(credential_id, False)),
                )
            ] = bool
        schema = vol.Schema(schema_fields)
        return self.async_show_form(step_id="init", data_schema=schema)
