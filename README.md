# UltraWideLock for Home Assistant

[![HACS validation](https://github.com/UWL-HA/UWL-Home-Assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/UWL-HA/UWL-Home-Assistant/actions/workflows/validate.yml)
[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=UWL-HA&repository=UWL-Home-Assistant&category=integration)

This custom integration brings an already commissioned
[UltraWideLock](https://github.com/ultrawidelock/ultrawidelock) into Home
Assistant through its existing Matter connection. It adds live UWB information,
history, configuration controls, and two dashboard cards without creating another
Matter fabric or CASE session.

## Entities

| Entity | Type | Description |
| --- | --- | --- |
| Lock | Lock | Standard Matter lock and unlock control |
| Auto-relock time | Number | Standard Door Lock auto-relock delay |
| Operating mode | Select | Normal or No remote lock/unlock |
| Actuator | Binary sensor | Standard Door Lock actuator status |
| UWB device in range | Binary sensor | Whether an authenticated credential is present |
| UWB distance | Sensor | Live distance in centimetres |
| UWB movement | Sensor | Unknown, stationary, approaching, or leaving |
| UWB credential | Sensor | Friendly name of the credential currently in range |
| UWB data status | Sensor | Live, stale, or unavailable subscription status |
| Last UWB update | Sensor | Timestamp of the latest live UWB update |
| Credential in range | Optional binary sensor | Occupancy for one selected credential |
| UWB event | Event | Detection, approach, threshold, lock, session outcome, and data-health events |
| Approach, unlock and relock distance | Numbers | UWB policy distances in centimetres |
| Motor time | Number | Local lock motor duration |
| UltraWideLock unlock/relock | Switches | Allow or prevent automatic local actions |
| Bound-lock unlock/relock | Switches | Allow or prevent automatic bound-lock actions |
| Last device seen | Sensors | Previous completed ranging session and time |
| Last device unlocked | Sensors | Credential, time, and distance of the last unlock |
| Bound lock | Diagnostic sensor | Friendly names and Matter endpoints of Door Lock bindings |

Unlock history follows native Matter Door Lock operation events. Because the
firmware does not emit another operation event when its reported state is already
unlocked, the integration also records the first enabled UWB unlock-threshold
crossing in each credential session.

Distance writes are validated before they reach Matter. Home Assistant requires
`unlock distance < approach distance < relock distance` and shows the current
values when a proposed change would break that order.

Credential IDs are collected automatically. Give them friendly names under
**Settings > Devices & services > UltraWideLock > Configure**. Select a credential
and give it a friendly device name. A Home Assistant notification points to this
screen when a new credential is discovered. Every newly detected credential
receives a standard occupancy binary sensor by default; disable the option on
the same credential screen to remove it. The pseudonymous raw ID remains
available as a state attribute.

The separate **UWB data freshness** configuration controls the stale-data timeout
(15 seconds by default). When an active UWB stream stops updating, its status
becomes `stale` and the live distance and movement entities are cleared. With no
device in range, the status is `unavailable`.

Under **Configure > Matter lock binding**, select an UltraWideLock to add or
remove a standard Matter Door Lock binding. Existing unrelated binding entries
are preserved. The integration verifies that the target ACL already grants the
UltraWideLock node CASE Operate access and never rewrites ACLs automatically.

The **UWB event** entity emits `device_detected`, `approach_started`,
`unlock_threshold_crossed`, `unlocked`, `approach_aborted`,
`left_without_unlock`, `left_after_unlock`, `device_left_range`, `relocked`,
`data_stale`, and `data_restored`. Each event includes the credential name and ID,
current and minimum distance, and session duration for automations.
It also reports whether the approach and unlock thresholds were reached, whether
the UltraWideLock unlocked, and the current UWB data status.

## Dashboard cards

Add either card through the Home Assistant dashboard editor and select the
UltraWideLock it should use:

- **UltraWideLock Overview** — live UWB status, lock control, configuration,
  automatic-action switches, and history.
- **UWB Approach Path** — animated approach view with distance, credential,
  movement, unlock zones, and lock control.

Both cards automatically find the entities belonging to the selected Matter
node. No YAML or individual sensor IDs are required. Restart Home Assistant after
installing or updating the integration so the bundled cards are loaded.

## Installation

### HACS

1. In HACS, open **Integrations > Custom repositories**.
2. Add `https://github.com/UWL-HA/UWL-Home-Assistant` as an **Integration**.
3. Download **UltraWideLock** and restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration**, search for
   **UltraWideLock**, and add it once. The setup flow lets you choose read-only
   operation or guides you through enabling writable custom controls.

### Manual

Copy `custom_components/uwb_matter` to
`/config/custom_components/uwb_matter`, restart Home Assistant, and add
**UltraWideLock** under **Settings > Devices & services**.

## Optional writable controls

Reading UWB data needs no additional setup. Writing manufacturer-specific
settings requires the included Matter Server schema. New installations are
guided through these steps directly in the integration setup flow; the commands
are repeated here for reference.

Run in the **Terminal & SSH** add-on:

```sh
sh /homeassistant/custom_components/uwb_matter/install_matter_schema.sh
```

Then open the Matter Server add-on and go to **Configuration**. Press the three
dots, select **Edit in YAML**, and add this at the bottom:

```yaml
matter_server_env_vars:
  - NODE_OPTIONS=--import=/config/ultrawidelock-cluster.mjs
```

Save and restart the Matter Server add-on, then restart Home Assistant Core.
Repeat the installer command after an integration update when the bundled schema
has changed. This entire step is optional for read-only use.

## Requirements and compatibility

- A commissioned Matter device exposing manufacturer cluster `0xFFF1FC10` on
  endpoint 1.
- Home Assistant's Matter integration and Matter Server.
- Initially developed against Home Assistant 2026.8 and Matter Server 1.4.0.

The integration reads the raw subscribed attribute cache because the custom UWB
attributes are not part of the standard Matter schema.

## License

[MIT](LICENSE)
