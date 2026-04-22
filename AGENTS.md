# Home Assistant — Blueprint & Automation Notes

Hard-won lessons from building the BILRESA dimmer blueprint. Optimized for the next agent picking up this directory.

## Tools

The `tools/` folder wraps the common HA websocket calls. Credentials come from `.env` (copy `.env.example`; `HA_URL` + `HA_TOKEN`). Prefer these over ad-hoc Python:

| Command | Use for |
|---|---|
| `tools/push_blueprint.py <file.yaml>` | Push a local blueprint + reload (handles the `source_url` cache trap) |
| `tools/reload_automations.py` | Reload without pushing |
| `tools/system_log.py [substr] [-l ERROR]` | Filter HA's system log — **first stop for debugging** |
| `tools/watch_events.py [-f substr] [--services light]` | Live-print `state_changed` + `call_service` |

For anything outside these, use the `HA` context manager in `tools/ha.py` (`ha.rpc(...)`, `ha.subscribe(...)`, `ha.events(...)`).

## Debugging workflow (in order)

1. **Check `system_log/list` first, not traces.** Trace buffers get flooded with unrelated `state_changed` events; the system log has the actual Jinja/Python errors. Via websocket: `{"type": "system_log/list"}`.
2. **`render_template`** (websocket) is the fastest way to test a Jinja expression against real HA state without touching the automation. Pass the entity_id literally; verify each step before assembling.
3. **Subscribe to `state_changed`, `call_service`, `automation_triggered`** simultaneously when reproducing a bug. If the automation fires but no service call follows, the action is failing silently — read `system_log/list`.
4. **Bump `stored_traces`** on the automation config (default 5) when hunting a specific trigger — otherwise unrelated state changes displace the trace you want.
5. **Device & entity discovery**: `config/device_registry/list` + `config/entity_registry/list`. Match entities to devices via `device_id`.

## Blueprint pitfalls

- **`{{ }}` in `variables:` stringifies dicts.** Never store `trigger.event.data.new_state` (or any object) in a variable — it becomes the string `"<State ...>"`, then `.attributes.X` fails with `'str object' has no attribute 'attributes'`. Inline the full path instead:
  ```yaml
  # WRONG — new_state becomes a string
  variables:
    new_state: "{{ trigger.event.data.new_state }}"
    event_type: "{{ new_state.attributes.event_type }}"

  # RIGHT — leaf scalars are fine
  variables:
    event_type: "{{ trigger.event.data.new_state.attributes.event_type }}"
  ```
  Leaf scalars (strings, ints, lists) survive the round-trip; nested dicts don't.

- **State triggers can't template `entity_id`.** If you want a blueprint with a device selector that covers N devices:
  ```yaml
  trigger: [{ platform: event, event_type: state_changed }]
  condition:
    - "{{ trigger.event.data.entity_id.startswith('event.') }}"
    - "{{ device_id(trigger.event.data.entity_id) == my_device }}"
  ```
  Downside: trigger fires on every state change in HA. Conditions fail fast for non-matches, so it's cheap, but the trace buffer churns.

- **Feedback loops with `platform: event`.** When the automation's own state changes (current, last_triggered) fire `state_changed`, it re-triggers itself. Harmless if conditions filter by entity domain, but eats trace slots. Consider adding `"{{ not trigger.event.data.entity_id.startswith('automation.') }}"` as a first condition to stop the retriggers early.

- **`brightness_step_pct` is cumulative per call.** If the event carries a burst count (e.g. IKEA `multi_press_8` = 8 ticks), multiplying by `dim_step` can easily overshoot ±100%. Clamp the delta:
  ```yaml
  delta: "{{ [-50, [50, raw_delta] | min] | max }}"
  ```

- **Sensor state strings get auto-coerced to int in `variables:`.** If the state is `"0"` or `"1"` (common for binary-ish sensors like Matter switch positions), HA turns it into the int `0`/`1` when you assign it to a variable. Comparing against string literals (`== '0'`) then silently fails. Cast explicitly and compare as ints:
  ```yaml
  # WRONG — HA coerces, '0' never matches
  new_val: "{{ trigger.event.data.new_state.state }}"
  condition: "{{ new_val == '0' }}"

  # RIGHT
  new_val: "{{ trigger.event.data.new_state.state | int(-1) }}"
  condition: "{{ new_val == 0 }}"
  ```

## Deployment / cache trap

**HA does not re-fetch `source_url` blueprints automatically.** Once imported, the blueprint lives at `/config/blueprints/automation/<namespace>/<file>.yaml`. Pushing to GitHub does nothing — HA keeps serving the cached copy.

Use `tools/push_blueprint.py <file.yaml>` — it calls `blueprint/save` with `allow_override: True` (HA rejects the call without that flag) and reloads automations. Existing automation instances keep their saved input values across blueprint updates, so changing a default doesn't propagate to them.

## Event entities (Matter / Zigbee buttons)

- State of an `event.*` entity is an **ISO timestamp** (when it last fired). `attributes.event_type` carries the event kind (e.g. `multi_press_1`, `long_press`).
- State triggers fire on every new timestamp (even if `event_type` repeats), so no extra debouncing needed.
- Second-instance devices get entity_ids suffixed with `_2` (`event.foo_button_1_2`). If your blueprint regexes the button number from the entity_id, match `_button_(\d+)(?:_\d+)?$`. Safer: extract from `friendly_name` attribute.
- Device triggers (`platform: device`) are **not** exposed for `event.*` entities by most integrations. Use `platform: state` on the entity directly.

## BILRESA scroll wheel endpoint mapping (IKEA, Matter)

9 switch endpoints, three per dot. Each dot has: CW rotation, CCW rotation, physical press (with long-press support).

| Dot | CW | CCW | Press |
|---|---|---|---|
| 1 | button_1 | button_2 | button_3 |
| 2 | button_4 | button_5 | button_6 |
| 3 | button_7 | button_8 | button_9 |

`multi_press_N` on rotation endpoints ≈ tick count in that burst (reported as one debounced event). Rotation endpoint itself identifies the active dot — you don't need to track dot state in HA.
