#!/usr/bin/env python3
"""Display the feeder's schedules: python -m examples.show_schedules."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Load the library shipped inside the integration; Home Assistant is not needed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components/netizen_ble"))
from petnetizen_feeder import FeederDevice, Weekday  # noqa: E402

DEFAULT_ADDRESS = "B8:E3:EC:45:CC:F2"
_LOGGER = logging.getLogger(__name__)


async def show_schedules(
    address: str, device_type: str, verification_code: str | None = None
) -> None:
    feeder = FeederDevice(
        address,
        device_type=device_type,
        verification_code=verification_code,
        auto_sync_time=False,
    )
    try:
        async with asyncio.timeout(45):
            print(f"Connecting to {address}...", flush=True)
            if not await feeder.connect():
                raise RuntimeError(
                    "Could not connect. Check Bluetooth, feeder range, and device type. "
                    "Close the phone app or disconnect Home Assistant if it is using "
                    "the feeder. Use --debug for details."
                )
            schedules = await feeder.query_schedule()
    finally:
        # Also clean up a partially established connection when connect() fails.
        async with asyncio.timeout(5):
            await feeder.disconnect()

    if not schedules:
        print(
            "No schedule entries returned. The schedule may be empty, or the "
            "feeder may not have returned a readable response. "
            "Run with --debug to inspect the response."
        )
        return

    print(f"\nSchedules for {address} (times as stored on the feeder):")
    print(f"{'#':>2}  {'Time':5}  {'Portions':>8}  {'Status':8}  Days")
    for index, schedule in enumerate(schedules, start=1):
        weekdays = schedule["weekdays"]
        if set(weekdays) == set(Weekday.ALL_DAYS):
            days = "Every day"
        else:
            days = ", ".join(day.title() for day in weekdays) or "No days selected"
        status = "Enabled" if schedule["enabled"] else "Disabled"
        print(f"{index:>2}  {schedule['time']:5}  {schedule['portions']:>8}  {status:8}  {days}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Connect over Bluetooth and display the feeder's stored schedules."
    )
    parser.add_argument(
        "address",
        nargs="?",
        default=DEFAULT_ADDRESS,
        help=f"feeder Bluetooth address (default: {DEFAULT_ADDRESS})",
    )
    parser.add_argument(
        "--device-type",
        choices=("standard", "jk", "ali"),
        default="standard",
        help="Bluetooth service type (default: standard)",
    )
    parser.add_argument("--debug", action="store_true", help="show Bluetooth debug logs")
    parser.add_argument(
        "--verification-code",
        help="optional 8-digit hexadecimal family ID (default: omit verification)",
    )
    args = parser.parse_args()
    if args.verification_code is not None:
        try:
            code = bytes.fromhex(args.verification_code)
        except ValueError:
            parser.error("--verification-code must contain exactly 8 hexadecimal digits")
        if len(args.verification_code) != 8 or len(code) != 4:
            parser.error("--verification-code must contain exactly 8 hexadecimal digits")
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    address = args.address.strip().upper().replace("-", ":")
    try:
        asyncio.run(show_schedules(address, args.device_type, args.verification_code))
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        _LOGGER.error("%s", str(exc) or "Bluetooth operation timed out.", exc_info=args.debug)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
