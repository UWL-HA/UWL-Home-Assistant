# UltraWideLock for Home Assistant

[![HACS validation](https://github.com/UWL-HA/UWL-Home-Assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/UWL-HA/UWL-Home-Assistant/actions/workflows/validate.yml)
[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=UWL-HA&repository=UWL-Home-Assistant&category=integration)

This custom integration adds live UWB data, controls, history and dashboard
cards for an already commissioned
[UltraWideLock](https://github.com/ultrawidelock/ultrawidelock). It uses the
existing Home Assistant Matter connection and does not create another Matter
fabric or session.

## What it provides

| Group | Entities and features |
| --- | --- |
| Lock | Lock/unlock control, lock state, operating mode and auto-relock time |
| Live UWB | Device in range, distance in cm, movement, current credential, data status and last update |
| Distances | Configurable approach, unlock and relock distances |
| Actions | Switches for local and bound-lock unlock/relock behavior, plus motor time |
| History | Last device seen, last device unlocked, timestamps and unlock distance |
| Credentials | Optional occupancy sensor and friendly name for each detected credential |
| Binding | Bound-lock status and details, with guided Matter binding management |
| Events | UWB session events for detection, approach, threshold crossing, unlock, departure and relock |

The integration includes two cards that can be added through the dashboard UI:

- **UltraWideLock Overview** combines status, configuration, controls and history.
- **UWB Approach Path** visualizes a credential approaching the lock.

Select an UltraWideLock in the card editor; its related entities are found
automatically.

## Settings

Open **Settings > Devices & services > UltraWideLock > Configure** to:

- set the stale-data timeout;
- name detected credentials and enable or remove their occupancy sensors;
- add or remove a standard Matter Door Lock binding.

Distance changes are validated before writing and must satisfy
`unlock distance < approach distance < relock distance`.

## Installation with HACS

1. In HACS, add `https://github.com/UWL-HA/UWL-Home-Assistant` as a custom
   **Integration** repository.
2. Download **UltraWideLock** and restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and select
   **UltraWideLock**.
4. Choose read-only setup or follow the setup flow to enable writable controls.

For manual installation, copy `custom_components/uwb_matter` to
`/config/custom_components/uwb_matter`, restart Home Assistant and add the
integration.

## Optional writable controls

Reading requires no additional setup. To write manufacturer-specific settings,
install the included Matter Server schema from **Terminal & SSH**:

```sh
sh /homeassistant/custom_components/uwb_matter/install_matter_schema.sh
```

Then open **Settings > Apps > Matter Server > Configuration**, press the three
dots, choose **Edit in YAML**, and add:

```yaml
matter_server_env_vars:
  - NODE_OPTIONS=--import=/config/ultrawidelock-cluster.mjs
```

Save and restart Matter Server, then restart Home Assistant. Repeat the installer
command after an integration update if the bundled schema changed.

## Requirements

- Home Assistant with the Matter integration and Matter Server
- An UltraWideLock exposing manufacturer cluster `0xFFF1FC10` on endpoint 1

## License

[MIT](LICENSE)
