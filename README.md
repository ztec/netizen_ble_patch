# Pet Netizen BLE — bundled patch

Home Assistant integration for Pet Netizen / CloudPets / Du Bluetooth feeders,
based on [lorek123/netizen_ble](https://github.com/lorek123/netizen_ble).
The patched Python feeder library is included inside the integration folder.
Home Assistant does **not** install `petnetizen-feeder` from PyPI.

## Manual installation

1. Download or clone this repository.
2. Copy the entire `custom_components/netizen_ble` directory into your Home
   Assistant configuration's `custom_components` directory. The final path must
   be `/config/custom_components/netizen_ble/manifest.json`, with the bundled
   `petnetizen_feeder` directory beside it.
3. Restart Home Assistant.
4. For a new device, open **Settings → Devices & services → Add integration →
   Pet Netizen BLE**. Enter its Bluetooth address or use discovery.
5. Leave **Use a verification code** off for the tested DU-F09B.

This fork keeps the `netizen_ble` domain and existing entity identifiers.
If the upstream integration is already installed, back up its directory and
replace it with this one; keep the existing Home Assistant device entry.
Do not install two copies of that domain. If HACS manages the upstream copy,
stop updating that copy through HACS, since an update would replace this patch.

Home Assistant still installs the normal Bluetooth transport dependencies
(`bleak` and `bleak-retry-connector`). You do not need to install the bundled
feeder library separately or edit Python packages inside Home Assistant.

## Connection options

Existing devices can change these through the integration's **Configure**
button. Saving options reloads the entry.

| Option | Default | Behavior |
| --- | --- | --- |
| Use a verification code | Off | Omits the `SET_FAMILY_ID` packet, including after reconnecting. |
| Verification code | `00000000` | Used only when verification is enabled; exactly eight hexadecimal digits. |
| Automatically synchronize the feeder clock | Off | Answers device clock-sync requests when enabled. The explicit **Sync time** button remains available. |

Old entries containing `verification_code: "00000000"` also start with
verification off. A saved custom code is retained but only sent after enabling
the option. A family ID is not necessarily a PIN you chose in the phone app.

## Included functionality

The upstream entities and actions remain available: schedule display and
editing, manual feeding, portions, child lock, sound, device status, time sync,
and model-specific controls. Their availability depends on the feeder model.
Live validation for this patch used schedule reads and connection keep-alives;
feeding, schedule changes, clock changes, and reset commands were not tested.

The bundled library adds optional verification, clock-sync suppression, a fix
for heartbeat acknowledgment loops, and a quiet MTU fallback for BlueZ.
See [connection findings](docs/connection-notes.md) for the observed behavior
and remaining limitations.

## Read schedules without Home Assistant

From the repository root, with Python 3.12 or newer:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'bleak>=2.1.0'
.venv/bin/python examples/show_schedules.py
```

The example defaults to `B8:E3:EC:45:CC:F2`. Supply another address as the first
argument, or use `--debug` for logs. It imports the included library and does
not feed, modify schedules, or synchronize the clock. Close other Bluetooth
clients while running it.

## Development

The integration and its bundled library are in
`custom_components/netizen_ble/`. Update the library there; there is no second
copy and no runtime download of the upstream feeder package.

Tests use Home Assistant 2026.9.4 and Python 3.14:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check custom_components tests examples/show_schedules.py
```

Tests cover bundled imports, default and explicit verification, configuration
and options flows, Home Assistant setup, direct and supplied Bluetooth clients,
reconnection, schedule decoding, clock-sync suppression, and heartbeat replies.
They do not connect to physical hardware. CI runs the same checks.

## Attribution

Based on the MIT-licensed upstream integration and feeder library.
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) records their exact source
revisions and retained license information.
