"""Connection regressions based on a DU-F09B rejecting the default family ID."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from petnetizen_feeder import FeederDevice
from petnetizen_feeder.protocol import FeederBLEProtocol

ADDRESS = "B8:E3:EC:45:CC:F2"
# Captured from the feeder: five enabled daily meals, with no count prefix.
SCHEDULE = bytes.fromhex("eb11197f070002017f090002017f0a0001017f0c0001017f1500010100ae")


class FakeClient:
    def __init__(self):
        self.is_connected = True
        self.writes = []
        self.notify = None
        characteristic = SimpleNamespace(
            properties=["write-without-response"], max_write_without_response_size=20
        )
        service = SimpleNamespace(get_characteristic=lambda _: characteristic)
        self.services = SimpleNamespace(get_service=lambda _: service)

    @property
    def mtu_size(self):
        raise AssertionError("Do not read BlueZ's unacquired MTU property")

    async def connect(self):
        self.is_connected = True

    async def disconnect(self):
        self.is_connected = False

    async def start_notify(self, characteristic, callback):
        self.notify = callback

    async def stop_notify(self, characteristic):
        self.notify = None

    async def write_gatt_char(self, characteristic, data, *, response):
        self.writes.append(bytes(data))
        if data[1] == 0x11:
            assert self.notify is not None
            self.notify(characteristic, bytearray(SCHEDULE))


@pytest.fixture
def fast_sleep(monkeypatch):
    original_sleep = asyncio.sleep

    async def sleep(_delay):
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)


@pytest.mark.parametrize("code", [None, "00000000", "01020304"])
@pytest.mark.parametrize("provided_client", [False, True])
async def test_connect_and_reconnect_family_id_policy(
    code, provided_client, monkeypatch, fast_sleep
):
    clients = [FakeClient(), FakeClient()]
    new_clients = iter(clients)
    monkeypatch.setattr(
        "petnetizen_feeder.protocol.BleakClient", lambda *a, **kw: next(new_clients)
    )
    feeder = FeederDevice(ADDRESS, verification_code=code, auto_sync_time=False)
    monkeypatch.setattr(feeder, "_start_heartbeat", Mock())
    try:
        for client, connect in zip(clients, [feeder.connect, feeder.reconnect]):
            assert await connect(ble_client=client if provided_client else None)
            slots = await feeder.query_schedule()
            assert [(s["time"], s["portions"]) for s in slots] == [
                ("07:00", 2),
                ("09:00", 2),
                ("10:00", 1),
                ("12:00", 1),
                ("21:00", 1),
            ]
            assert all(s["enabled"] and len(s["weekdays"]) == 7 for s in slots)
            expected = [bytes.fromhex("ea110000ae")]
            if code is not None:
                expected.insert(0, bytes.fromhex(f"ea0604{code}00ae"))
            assert client.writes == expected
            client.is_connected = False
    finally:
        await feeder.disconnect()


async def test_factory_reconnect_preserves_no_verification(monkeypatch, fast_sleep):
    first, replacement = FakeClient(), FakeClient()
    factory = AsyncMock(return_value=replacement)
    feeder = FeederDevice(ADDRESS, verification_code=None, connection_factory=factory)
    monkeypatch.setattr(feeder, "_start_heartbeat", Mock())
    try:
        assert await feeder.connect(ble_client=first)
        first.is_connected = False
        assert await feeder.ensure_connected()
        factory.assert_awaited_once()
        assert len(await feeder.query_schedule()) == 5
        assert first.writes == []
        assert replacement.writes == [bytes.fromhex("ea110000ae")]
    finally:
        await feeder.disconnect()


async def test_notification_failure_does_not_start_heartbeat(monkeypatch, fast_sleep):
    client = FakeClient()
    client.start_notify = AsyncMock(side_effect=RuntimeError("notifications failed"))
    feeder = FeederDevice(ADDRESS, verification_code=None)
    heartbeat = Mock()
    monkeypatch.setattr(feeder, "_start_heartbeat", heartbeat)
    try:
        assert not await feeder.connect(ble_client=client)
        assert not feeder.is_connected
        assert client.writes == []
        heartbeat.assert_not_called()
    finally:
        await feeder.disconnect()


@pytest.mark.parametrize("auto_sync_time", [False, True])
async def test_device_time_request_can_be_observed_without_writing(auto_sync_time):
    protocol = FeederBLEProtocol(ADDRESS, auto_sync_time=auto_sync_time)
    protocol.send_sync_time = AsyncMock()
    request = bytearray.fromhex("eb050000ae")
    protocol.notification_handler(None, request)
    await asyncio.sleep(0)
    assert protocol.received_data == [request]
    assert protocol.send_sync_time.await_count == int(auto_sync_time)


@pytest.mark.parametrize("payload_limit", [20, 244])
async def test_mtu_fallback_uses_characteristic(payload_limit):
    protocol = FeederBLEProtocol(ADDRESS)
    protocol.client = FakeClient()
    protocol.write_characteristic = SimpleNamespace(max_write_without_response_size=payload_limit)
    assert await protocol._request_mtu() == payload_limit + 3


async def test_backend_mtu_request_is_preserved():
    protocol = FeederBLEProtocol(ADDRESS)
    request = AsyncMock(return_value=247)
    protocol.client = SimpleNamespace(_backend=SimpleNamespace(request_mtu=request))
    assert await protocol._request_mtu(512) == 247
    request.assert_awaited_once_with(512)


@pytest.mark.parametrize("device_initiated", [False, True])
async def test_heartbeat_acknowledgment_does_not_create_echo_loop(device_initiated):
    protocol = FeederBLEProtocol(ADDRESS)
    protocol.client = FakeClient()
    reply = bytearray.fromhex("eb030000ae")

    async def acknowledge(*args, **kwargs):
        protocol.notification_handler(None, reply)

    protocol.client.write_gatt_char = AsyncMock(side_effect=acknowledge)
    if device_initiated:
        protocol.notification_handler(None, reply)
    else:
        assert await protocol.send_heartbeat()
    for _ in range(3):
        await asyncio.sleep(0)
    protocol.client.write_gatt_char.assert_awaited_once()
    assert protocol._heartbeat_ack_pending is False
