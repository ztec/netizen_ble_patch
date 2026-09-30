# Changelog

## 3.0.0

- Bundle the patched feeder library inside the Home Assistant integration.
- Omit family-ID verification by default, including for existing device entries.
- Add configuration options for verification and automatic clock sync.
- Preserve explicit verification codes, entity identifiers, and the integration
  domain from the upstream integration.
- Prevent repeated heartbeat acknowledgment echoes and avoid the BlueZ MTU
  warning when no explicit MTU request is available.
- Include a standalone schedule reader, installation instructions, provenance,
  and regression tests using Home Assistant 2026.9.4.
