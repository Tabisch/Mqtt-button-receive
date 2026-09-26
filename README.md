# MQTT Button Receive

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/tabisch/mqtt-button-receive/actions/workflows/validate.yml/badge.svg)](https://github.com/tabisch/mqtt-button-receive/actions/workflows/validate.yml)

A Home Assistant custom integration that listens to an MQTT topic and emulates a
physical button. Each matching message fires a button **event entity**
(`event.<name>`) that you can use as an automation trigger — just like the
buttons of Zigbee, Z-Wave or Shelly devices.

- Configurable topic (wildcards `+` / `#` supported) and QoS
- Optional template to filter messages and map them to event types
  (`press`, `double_press`, `long_press`, or your own)
- Set up and edited entirely in the UI; add as many buttons as you like
- Also fires `mqtt_button_receive_event` on the event bus

## Requirements

- Home Assistant 2024.11 or newer
- The [MQTT integration](https://www.home-assistant.io/integrations/mqtt/) set up
  and connected to your broker

## Installation

### HACS (recommended)

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/tabisch/mqtt-button-receive` with type **Integration**.
3. Search for **MQTT Button Receive**, download it, and restart Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tabisch&repository=mqtt-button-receive&category=integration)

### Manual

Copy `custom_components/mqtt_button_receive` into the `custom_components`
folder of your Home Assistant configuration and restart.

## Configuration

**Settings → Devices & services → Add integration → MQTT Button Receive**

| Field | Description |
| --- | --- |
| Name | Name of the button device/entity. |
| MQTT topic | Topic to subscribe to. `+` and `#` wildcards are allowed. |
| Filter template | Optional. Decides whether a message is a press and which event type it is (see below). |
| Event types | Event types the button can fire. The **first** one is the default. Defaults to `press`, `double_press`, `long_press`. |
| QoS | MQTT QoS for the subscription. |

Everything except the name can be changed later via **Configure**.

### Filter template

The template is rendered for every message with these variables:

| Variable | Content |
| --- | --- |
| `value` | Raw payload as a string |
| `value_json` | Payload parsed as JSON (undefined if the payload is not JSON) |
| `topic` | Topic the message arrived on (useful with wildcards) |

The result decides what happens:

| Template result | Effect |
| --- | --- |
| Name of a configured event type, e.g. `double_press` | Fires that event type |
| `true`, `on`, `yes`, `1` | Fires the first (default) event type |
| Anything else (`false`, empty, …) | Message is ignored |

Without a template **every** message on the topic fires the default event type.

#### Examples

Only react to the payload `ON`:

```jinja
{{ value == 'ON' }}
```

Only react to a specific JSON field value:

```jinja
{{ value_json is defined and value_json.button == 'kitchen' and value_json.state == 'pressed' }}
```

Map Zigbee2MQTT-style actions to event types:

```jinja
{% set map = {'single': 'press', 'double': 'double_press', 'hold': 'long_press'} %}
{{ map.get(value_json.action, '') if value_json is defined else '' }}
```

Filter by sub-topic when using a wildcard topic such as `home/+/button`:

```jinja
{{ topic == 'home/garage/button' }}
```

## Using it in automations

The event entity's state is the timestamp of the last press; its `event_type`
attribute holds the type. Trigger on it with a state trigger:

```yaml
triggers:
  - trigger: state
    entity_id: event.hall_button
    not_to: unavailable
conditions:
  - condition: state
    entity_id: event.hall_button
    attribute: event_type
    state: double_press
actions:
  - action: light.toggle
    target:
      entity_id: light.hall
```

Or listen for the bus event, which carries `entity_id`, `event_type`, `topic`
and `payload`:

```yaml
triggers:
  - trigger: event
    event_type: mqtt_button_receive_event
    event_data:
      entity_id: event.hall_button
      event_type: press
```

## Development

```bash
pip install -r requirements_test.txt
pytest
```
