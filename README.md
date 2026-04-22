# ha-blueprints

Home Assistant blueprints and debug tooling.

## Blueprints

### `bilresa_three_light_dimmer.yaml`

Control three lights with an IKEA BILRESA scroll wheel (Matter).

- **Rotate** → dim the light on the currently-selected dot (CW brighter, CCW dimmer; delta clamped to ±50% per event)
- **Short press** a dot button → toggle that dot's light
- **Long press** a dot button → apply a per-dot scene (configurable color + brightness)

Pick a remote via the device selector, pick three light entities, adjust the dim step and long-press scenes.

**Install via the HA UI:**

1. Settings → Automations & Scenes → Blueprints → **Import blueprint**
2. Paste: `https://raw.githubusercontent.com/bitkill/ha-blueprints/refs/heads/main/bilresa_three_light_dimmer.yaml`
3. Create an automation from the imported blueprint.

## Debug tooling

### `bilresa_debug.html`

Single-file browser debug page that connects to your HA WebSocket and visualizes every BILRESA in real time: active dot, rotation direction + tick count, all 9 button endpoints, and auto-detected target lights (inferred from state changes within 750 ms of a button event).

Open the file in a browser, paste your HA WebSocket URL + long-lived access token, and it connects directly — no server required.

## Notes

- `AGENTS.md` — lessons learned from writing and debugging these blueprints (gotchas, debugging workflow, deployment cache trap).
