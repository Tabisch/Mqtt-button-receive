"""Constants for the MQTT Button Receive integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "mqtt_button_receive"

CONF_TOPIC: Final = "topic"
CONF_QOS: Final = "qos"
CONF_VALUE_TEMPLATE: Final = "value_template"
CONF_EVENT_TYPES: Final = "event_types"

DEFAULT_NAME: Final = "MQTT Button"
DEFAULT_QOS: Final = 0
DEFAULT_EVENT_TYPES: Final = ["press", "double_press", "long_press"]

# Template results that mean "the button was pressed" (fires the default event type).
TRUTHY_RESULTS: Final = frozenset({"true", "on", "yes", "1"})

# Event fired on the Home Assistant event bus for every accepted press.
BUS_EVENT: Final = f"{DOMAIN}_event"
