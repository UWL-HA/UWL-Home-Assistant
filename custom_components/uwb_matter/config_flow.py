"""Config flow for UltraWideLock Matter sensors."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import CONF_CREDENTIAL_NAMES, DOMAIN


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
        """Show one editable name for every observed credential ID."""
        credentials = dict(
            self.config_entry.options.get(CONF_CREDENTIAL_NAMES, {})
        )
        if user_input is not None:
            names = {
                credential_id: str(user_input.get(credential_id, "")).strip()
                for credential_id in credentials
            }
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_CREDENTIAL_NAMES: names},
            )

        schema = vol.Schema(
            {
                vol.Optional(credential_id, default=name): str
                for credential_id, name in sorted(credentials.items())
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
