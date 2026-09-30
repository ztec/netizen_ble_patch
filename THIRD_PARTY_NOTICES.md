# Third-party code

## Home Assistant integration

- Source: https://github.com/lorek123/netizen_ble
- Revision: `93b873f48a9bd1ab21b3b9a34b5d0f215778fe14`
- Author: lorek123 and upstream contributors.
- Upstream declares the MIT license in its README. That source revision does
  not contain a separate LICENSE file.
- Included in `custom_components/netizen_ble/`, excluding its bundled
  `petnetizen_feeder` subpackage, and the dashboard examples.

Modifications include bundled relative imports, configurable opt-in
verification, optional automatic clock sync, updated package metadata, tests,
and installation documentation. Integration domain and entity identifiers are
preserved.

## Feeder library

- Source: https://github.com/lorek123/petnetizen_feeder
- Revision: `ea988fc3c51c8f034464f200d2ea4be0912c3a72`
- Version: 0.5.7, with local connection patches.
- Copyright (c) 2025 Petnetizen Feeder contributors.
- License: MIT; the original text is retained in
  `custom_components/netizen_ble/petnetizen_feeder/LICENSE`.
- Included directly as `custom_components/netizen_ble/petnetizen_feeder/`.

Modifications add `verification_code=None`, optional clock-sync replies,
heartbeat acknowledgment tracking, and a BlueZ MTU fallback. The package's
local version is `0.5.7+bundled.1`. The standalone schedule example and library
regression tests accompany it.
