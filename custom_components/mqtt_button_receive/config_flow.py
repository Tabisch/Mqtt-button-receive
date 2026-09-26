"""Config flow for MQTT Button Receive."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_EVENT_TYPES,
    CONF_QOS,
    CONF_TOPIC,
    CONF_VALUE_TEMPLATE,
    DEFAULT_EVENT_TYPES,
    DEFAULT_NAME,
    DEFAULT_QOS,
    DOMAIN,
)


def _settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema for the settings shared by the user step and the options flow."""
    return vol.Schema(
        {
            vol.Required(
                CONF_TOPIC, default=defaults.get(CONF_TOPIC, vol.UNDEFINED)
            ): selector.TextSelector(),
            vol.Optional(
                CONF_VALUE_TEMPLATE,
                description={"suggested_value": defaults.get(CONF_VALUE_TEMPLATE)},
            ): selector.TemplateSelector(),
            vol.Required(
                CONF_EVENT_TYPES,
                default=defaults.get(CONF_EVENT_TYPES, DEFAULT_EVENT_TYPES),
            ): selector.TextSelector(selector.TextSelectorConfig(multiple=True)),
            vol.Required(
                CONF_QOS, default=str(defaults.get(CONF_QOS, DEFAULT_QOS))
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["0", "1", "2"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _validate_settings(
    user_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate and normalize user input. Returns (settings, errors)."""
    errors: dict[str, str] = {}
    settings: dict[str, Any] = {}

    topic = user_input[CONF_TOPIC].strip()
    try:
        mqtt.valid_subscribe_topic(topic)
    except vol.Invalid:
        errors[CONF_TOPIC] = "invalid_topic"
    settings[CONF_TOPIC] = topic

    # Template syntax is already validated by the TemplateSelector.
    if value_template := (user_input.get(CONF_VALUE_TEMPLATE) or "").strip():
        settings[CONF_VALUE_TEMPLATE] = value_template

    event_types: list[str] = []
    for raw in user_input[CONF_EVENT_TYPES]:
        if not raw.strip():
            continue
        if (event_type := slugify(raw)) not in event_types:
            event_types.append(event_type)
    if not event_types:
        errors[CONF_EVENT_TYPES] = "no_event_types"
    settings[CONF_EVENT_TYPES] = event_types

    settings[CONF_QOS] = int(user_input[CONF_QOS])
    return settings, errors


class MqttButtonReceiveConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MQTT Button Receive."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            settings, errors = _validate_settings(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data={}, options=settings
                )

        schema = vol.Schema(
            {vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector()}
        ).extend(_settings_schema(user_input or {}).schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return MqttButtonReceiveOptionsFlow()


class MqttButtonReceiveOptionsFlow(OptionsFlow):
    """Change the settings of an existing MQTT button."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            settings, errors = _validate_settings(user_input)
            if not errors:
                return self.async_create_entry(data=settings)

        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(user_input or dict(self.config_entry.options)),
            errors=errors,
        )
