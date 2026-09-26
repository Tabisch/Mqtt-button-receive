"""Tests for the MQTT Button Receive integration."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_mqtt_message,
)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mqtt_button_receive.const import (
    BUS_EVENT,
    CONF_EVENT_TYPES,
    CONF_QOS,
    CONF_TOPIC,
    CONF_VALUE_TEMPLATE,
    DEFAULT_EVENT_TYPES,
    DOMAIN,
)

ENTITY_ID = "event.test_button"


async def _setup(hass: HomeAssistant, **options: Any) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Button",
        options={
            CONF_TOPIC: "home/button",
            CONF_QOS: 0,
            CONF_EVENT_TYPES: DEFAULT_EVENT_TYPES,
            **options,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_every_message_is_press_without_template(
    hass: HomeAssistant, mqtt_mock
) -> None:
    await _setup(hass)
    events = async_capture_events(hass, BUS_EVENT)

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unknown"

    async_fire_mqtt_message(hass, "home/button", "anything")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["event_type"] == "press"
    assert state.attributes["payload"] == "anything"
    assert len(events) == 1
    assert events[0].data["event_type"] == "press"
    assert events[0].data["entity_id"] == ENTITY_ID


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('{"action": "single"}', "press"),
        ('{"action": "double"}', "double_press"),
        ('{"action": "hold"}', "long_press"),
        ('{"action": "release"}', None),
        ("not json", None),
    ],
)
async def test_template_maps_event_types(
    hass: HomeAssistant, mqtt_mock, payload: str, expected: str | None
) -> None:
    await _setup(
        hass,
        **{
            CONF_VALUE_TEMPLATE: (
                "{{ {'single': 'press', 'double': 'double_press', 'hold': 'long_press'}"
                ".get(value_json.action, '') if value_json is defined else '' }}"
            )
        },
    )
    events = async_capture_events(hass, BUS_EVENT)

    async_fire_mqtt_message(hass, "home/button", payload)
    await hass.async_block_till_done()

    if expected is None:
        assert events == []
        assert hass.states.get(ENTITY_ID).state == "unknown"
    else:
        assert [e.data["event_type"] for e in events] == [expected]
        assert hass.states.get(ENTITY_ID).attributes["event_type"] == expected


async def test_boolean_template_filter(hass: HomeAssistant, mqtt_mock) -> None:
    await _setup(hass, **{CONF_VALUE_TEMPLATE: "{{ value == 'ON' }}"})
    events = async_capture_events(hass, BUS_EVENT)

    async_fire_mqtt_message(hass, "home/button", "OFF")
    async_fire_mqtt_message(hass, "home/button", "ON")
    await hass.async_block_till_done()

    assert [e.data["payload"] for e in events] == ["ON"]


async def test_template_error_is_ignored(hass: HomeAssistant, mqtt_mock) -> None:
    await _setup(hass, **{CONF_VALUE_TEMPLATE: "{{ value_json.a.b }}"})
    events = async_capture_events(hass, BUS_EVENT)

    async_fire_mqtt_message(hass, "home/button", "{}")
    await hass.async_block_till_done()

    assert events == []


async def test_wildcard_topic(hass: HomeAssistant, mqtt_mock) -> None:
    await _setup(hass, **{CONF_TOPIC: "home/+/button"})
    events = async_capture_events(hass, BUS_EVENT)

    async_fire_mqtt_message(hass, "home/kitchen/button", "1")
    await hass.async_block_till_done()

    assert [e.data["topic"] for e in events] == ["home/kitchen/button"]


async def test_config_flow(hass: HomeAssistant, mqtt_mock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Hall",
            CONF_TOPIC: "home/#/bad",
            CONF_EVENT_TYPES: [" "],
            CONF_QOS: "1",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_TOPIC: "invalid_topic",
        CONF_EVENT_TYPES: "no_event_types",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Hall",
            CONF_TOPIC: " home/hall/button ",
            CONF_VALUE_TEMPLATE: "{{ value == 'ON' }}",
            CONF_EVENT_TYPES: ["Press", "press", "Triple Press"],
            CONF_QOS: "1",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hall"
    assert result["options"] == {
        CONF_TOPIC: "home/hall/button",
        CONF_VALUE_TEMPLATE: "{{ value == 'ON' }}",
        CONF_EVENT_TYPES: ["press", "triple_press"],
        CONF_QOS: 1,
    }


async def test_options_flow_reloads(hass: HomeAssistant, mqtt_mock) -> None:
    entry = await _setup(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_TOPIC: "home/other", CONF_EVENT_TYPES: ["press"], CONF_QOS: "0"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    events = async_capture_events(hass, BUS_EVENT)
    async_fire_mqtt_message(hass, "home/button", "x")
    async_fire_mqtt_message(hass, "home/other", "x")
    await hass.async_block_till_done()
    assert [e.data["topic"] for e in events] == ["home/other"]


async def test_unload(hass: HomeAssistant, mqtt_mock) -> None:
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    events = async_capture_events(hass, BUS_EVENT)
    async_fire_mqtt_message(hass, "home/button", "x")
    await hass.async_block_till_done()
    assert events == []
