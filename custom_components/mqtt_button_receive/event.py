"""Event entity that emulates a button driven by MQTT messages."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, TemplateError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.util.json import json_loads

from .const import (
    BUS_EVENT,
    CONF_EVENT_TYPES,
    CONF_QOS,
    CONF_TOPIC,
    CONF_VALUE_TEMPLATE,
    DEFAULT_EVENT_TYPES,
    DEFAULT_QOS,
    DOMAIN,
    TRUTHY_RESULTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MQTT button event entity."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT integration is not available")
    async_add_entities([MqttButtonEvent(hass, entry)])


class MqttButtonEvent(EventEntity):
    """An event entity that fires whenever a matching MQTT message arrives."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the entity from the config entry options."""
        options = entry.options
        self._topic: str = options[CONF_TOPIC]
        self._qos: int = options.get(CONF_QOS, DEFAULT_QOS)
        self._attr_event_types = list(
            options.get(CONF_EVENT_TYPES) or DEFAULT_EVENT_TYPES
        )
        self._template: Template | None = None
        if value_template := options.get(CONF_VALUE_TEMPLATE):
            self._template = Template(value_template, hass)

        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="MQTT Button Receive",
            model="MQTT button",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to the MQTT topic."""
        self.async_on_remove(
            await mqtt.async_subscribe(
                self.hass, self._topic, self._message_received, self._qos
            )
        )

    @callback
    def _message_received(self, msg: mqtt.ReceiveMessage) -> None:
        """Handle a new MQTT message."""
        payload = msg.payload
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")

        event_type = self._resolve_event_type(payload, msg.topic)
        if event_type is None:
            return

        attributes = {"topic": msg.topic, "payload": payload}
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
        self.hass.bus.async_fire(
            BUS_EVENT,
            {"entity_id": self.entity_id, "event_type": event_type, **attributes},
        )

    def _resolve_event_type(self, payload: str, topic: str) -> str | None:
        """Map a payload to an event type, or None if it should be ignored.

        Without a template every message is a press of the first event type.
        With a template, the rendered result decides:
          * the name of a configured event type -> that event type
          * true / on / yes / 1                 -> the first event type
          * anything else (false, empty, ...)   -> ignored
        """
        default_type = self._attr_event_types[0]
        if self._template is None:
            return default_type

        variables: dict[str, Any] = {"value": payload, "topic": topic}
        try:
            variables["value_json"] = json_loads(payload)
        except ValueError:
            pass

        try:
            rendered = self._template.async_render(variables, parse_result=False)
        except TemplateError as err:
            _LOGGER.warning(
                "Error rendering template for %s (topic %s, payload %r): %s",
                self.entity_id,
                topic,
                payload,
                err,
            )
            return None

        result = str(rendered).strip().lower()
        if result in self._attr_event_types:
            return result
        if result in TRUTHY_RESULTS:
            return default_type
        _LOGGER.debug(
            "Ignoring message on %s for %s: template returned %r",
            topic,
            self.entity_id,
            rendered,
        )
        return None
