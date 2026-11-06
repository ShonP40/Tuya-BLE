"""Bluetooth waits must honor Home Assistant cancellation and timeout scopes."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bleak_retry_connector import BleakNotFoundError

from custom_components.tuya_local_ble.tuya_ble import tuya_ble as transport
from custom_components.tuya_local_ble.tuya_ble.const import TuyaBLECode


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    def make_device(self):
        return transport.TuyaBLEDevice(
            None, SimpleNamespace(address="test-device", name="TY")
        )

    async def test_cancelled_connection_does_not_start_more_attempts(self):
        device = self.make_device()
        started = asyncio.Event()
        attempts = 0

        async def connect(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                started.set()
                await asyncio.Future()
            raise BleakNotFoundError()

        with (
            patch.object(transport, "establish_connection", side_effect=connect),
            patch.object(transport._LOGGER, "disabled", True),
        ):
            task = asyncio.create_task(device._ensure_connected())
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(attempts, 1)
        self.assertFalse(device._connect_lock.locked())

    async def test_cancelled_gatt_write_is_not_a_connection_error(self):
        device = self.make_device()
        device._client = SimpleNamespace(
            write_gatt_char=AsyncMock(side_effect=asyncio.CancelledError),
            is_connected=True,
        )
        device._disconnected = MagicMock()
        with (
            patch.object(transport._LOGGER, "disabled", True),
            self.assertRaises(asyncio.CancelledError),
        ):
            await device._int_send_packets_locked([b"packet"])
        device._disconnected.assert_not_called()

    async def test_cancelled_command_removes_pending_response(self):
        device = self.make_device()
        device._build_packets = MagicMock(return_value=[b"packet"])
        device._int_send_packet_while_connected = AsyncMock(
            side_effect=asyncio.CancelledError
        )
        with self.assertRaises(asyncio.CancelledError):
            await device._send_packet_while_connected(
                TuyaBLECode.FUN_SENDER_DEVICE_STATUS, b"", 0, True
            )
        self.assertEqual(device._input_expected_responses, {})
        self.assertFalse(device._operation_lock.locked())


if __name__ == "__main__":
    unittest.main()
