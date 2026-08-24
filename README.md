# UltraWideLock for Home Assistant

[![HACS validation](https://github.com/UWL-HA/UWL-Home-Assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/UWL-HA/UWL-Home-Assistant/actions/workflows/validate.yml)

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=UWL-HA&repository=UWL-Home-Assistant&category=integration)

This custom integration provides one focused Home Assistant device for an already
commissioned UltraWideLock. It reuses Home Assistant's existing Matter connection
and adds these entities:

- **Lock** — standard Matter lock and unlock control
- **Auto-relock time** — standard Door Lock configuration in seconds
- **Operating mode** — Normal or No remote lock/unlock
- **Actuator** — standard Door Lock actuator status
- **UWB device in range** — authenticated credential presence
- **UWB distance** — live distance in centimetres, unavailable when not ranging
- **UWB policy controls** — change approach, unlock and relock distances plus motor timing
- **UWB action switches** — independently allow or prevent automatic UltraWideLock
  unlock, UltraWideLock relock, bound-lock unlock, and bound-lock relock actions
- **UWB movement** — filtered unknown, stationary, approaching, or leaving state
- **UWB credential** — friendly name of the credential currently in range
- **Last device seen** — credential from the previous completed ranging session
- **Last device seen at** — timestamp when that previous session ended
- **Last device unlocked** — credential present at the last transition to Unlocked,
  or Unknown source when no credential was in range
- **Last device unlocked at** — timestamp of that unlock transition
- **Last unlocked at distance** — UWB distance in centimetres at that unlock

Credential IDs are collected automatically the first time they are observed.
Use **Settings > Devices & services > UltraWideLock > Configure** to give each
discovered ID a friendly name. The current credential appears in the normal Sensor
section, while its pseudonymous raw ID remains a state attribute.

Automatic discovery does not reload the integration. This prevents history
entities briefly becoming unavailable while a new credential is collected.

## Dashboard

The integration includes two dashboard cards:

- **UltraWideLock Overview** is the recommended complete interface. It groups
  live UWB status, lock control, every configurable distance and timer, operating
  mode, the four automatic-action switches, and device history in one responsive
  card.
- **UWB Approach Path** is the animated distance view. It shows the phone or watch
  moving toward the lock, the approach and unlock zones, credential, movement,
  live distance, and lock/unlock control.

Both cards only need one selected UltraWideLock. They use its unique Matter node
identifier to find all matching entities automatically, so multiple locks do not
become mixed and no sensor entity IDs need to be entered manually. They use
existing entities and do not add Matter or Thread traffic.

`dashboard-card.example.yaml` contains the complete overview card. Replace its
lock placeholder when using YAML, or add **UltraWideLock Overview** through the
visual dashboard editor and select the lock there. The approach card additionally
supports optional `approach_cm` and `session_cm` drawing overrides; the discovered
entities still supply the live firmware values. Restart Home Assistant after
installing or updating so the bundled cards are loaded. The integration registers
their shared card resource automatically in storage-mode dashboards.

When adding the card through the dashboard editor, select the lock from the
visual entity picker, which lists only locks provided by this integration. The
title is optional and otherwise follows the lock's friendly name. The
UltraWideLock device also adopts the user-assigned name of its matching native
Matter device, such as `Front door` or `Back door`, rather than the generic firmware
product name. YAML editing is not required.

The firmware must expose cluster `0xFFF1FC10` on endpoint 1. No additional Matter
fabric, controller, or CASE session is created by this integration.

Custom-cluster entities are created as soon as the cluster is discovered, even
when Home Assistant's Matter cache has not populated every attribute yet. This
keeps newly added firmware attributes from being left as unprovided entities.

## Install

### HACS

1. In HACS, open **Integrations** and select **Custom repositories**.
2. Add `https://github.com/UWL-HA/UWL-Home-Assistant` with
   category **Integration**.
3. Download **UltraWideLock** and restart Home Assistant.
4. Open **Settings > Devices & services > Add integration**, search for
   **UltraWideLock**, and add it once.

### Manual

1. Copy `custom_components/uwb_matter` from this directory to
   `/config/custom_components/uwb_matter` on Home Assistant.
2. Restart Home Assistant.
3. Open **Settings > Devices & services > Add integration**.
4. Search for **UltraWideLock** and add it once.

## Optional writable controls

No extra setup is required to read the custom UWB attributes. Live presence,
distance, movement, credential and history sensors work with the normal HACS
installation.

Writing manufacturer-specific settings requires Matter Server to know the custom
cluster's attribute types. The required schema and an installer script are bundled
with the integration. In the **Terminal & SSH** add-on, run:

```sh
sh /homeassistant/custom_components/uwb_matter/install_matter_schema.sh
```

The script copies the bundled file into Matter Server's configuration directory.
The equivalent manual command is:

```sh
cp /homeassistant/custom_components/uwb_matter/matter_schema/ultrawidelock-cluster.mjs \
  /addon_configs/core_matter_server/ultrawidelock-cluster.mjs
```

Then open the Matter Server add-on and go to **Configuration**. Press the three
dots in the upper-right corner and choose **Edit in YAML**. Add the following at
the bottom of the code:

```yaml
matter_server_env_vars:
  - NODE_OPTIONS=--import=/config/ultrawidelock-cluster.mjs
```

Save the configuration and restart the Matter Server add-on. Restart Home
Assistant Core afterwards. The number controls and four action switches can now
write their values to the lock. Run the installer script again after an
UltraWideLock update whenever its bundled Matter schema has changed.

This step is optional. Users who only want to view the UWB data should not add
the environment variable or install the Matter Server schema.

The integration only discovers commissioned Matter nodes that expose the custom
UWB cluster. Home Assistant's native Matter entities remain available separately;
they can be disabled if this focused UltraWideLock device is used as the primary
interface.

## Compatibility

Initially developed against Home Assistant 2026.8 and Matter Server 1.4.0. The
integration reads the raw subscribed attribute cache because manufacturer-specific
attributes have no standard Matter schema.
