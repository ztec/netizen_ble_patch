# DU-F09B connection findings

Validated locally on `B8:E3:EC:45:CC:F2`, advertised as
`Du-F09B_B8E3EC45CCF2`, using a Linux Bluetooth adapter.

## Rejected default family ID

The upstream library sends this packet during connection setup:

```text
EA 06 04 00 00 00 00 00 AE
```

With notifications enabled first, the feeder replies:

```text
EB 06 01 00 00 AE
```

That is a rejected verification response. The feeder then disconnects. The
upstream connection order sends verification before subscribing, so the reply
is missed and the eventual error says the device disconnected before
`start_notify`.

Without `SET_FAMILY_ID`, a schedule query (`EA 11 00 00 AE`) succeeds and
returns five enabled daily meals: 07:00 ×2, 09:00 ×2, 10:00 ×1, 12:00 ×1,
and 21:00 ×1 portions. These are the device's stored times.

The wrapper defaults to `verification_code=None` and preserves it through
reconnection. This was verified without resetting the feeder, changing its
app binding, or guessing PINs. Whether every control command works without
verification on every model remains untested.

## MTU warning

The BlueZ warning concerns reading an MTU value that Bleak has not acquired;
it did not prevent schedule replies, including a 30-byte notification. The
patched library uses the write characteristic's payload limit for the
informational fallback and retains explicit MTU requests on backends that
support them.

## Heartbeats and idle disconnects

The feeder acknowledges heartbeat packets. The upstream notification handler
echoed every heartbeat acknowledgment, creating repeated request/reply traffic.
The patched handler consumes the expected acknowledgment instead of echoing it.
Device-initiated heartbeat requests can still receive a single reply.

Short schedule reads succeeded repeatedly. Longer tests also observed the
feeder dropping its connection within several seconds when verification was
omitted. A permanently open connection has not been established. The library
retains reconnect-on-demand behavior through Home Assistant's connection
factory; this should not be treated as proof of ESPHome proxy compatibility.

The bundled library was tested across an idle drop and an explicit disconnect
using an externally supplied client and connection factory. Both subsequent
schedule queries reconnected successfully and returned the same five meals.
Two-second heartbeats during that bounded diagnostic were acknowledged once
each, without the earlier echo loop, but did not prevent the idle disconnect.
The production heartbeat interval remains unchanged at 60 seconds.

No Home Assistant deployment has been modified by creating this repository.
Unit tests run against Home Assistant's actual APIs with Bluetooth and setup
I/O mocked; physical validation uses the bundled Python library and a local
adapter. Device writes during validation were limited to the existing default
verification attempt, read queries, and heartbeats.
