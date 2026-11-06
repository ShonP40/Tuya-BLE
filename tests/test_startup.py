"""Startup behavior when a BLE device is slow or unavailable."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components import tuya_local_ble as integration


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_initial_update_does_not_hold_entry_setup(self):
        started = asyncio.Event()
        release = asyncio.Event()
        background_tasks = []

        async def slow_update():
            started.set()
            await release.wait()

        device = MagicMock()
        device.product_id = "qycalacn"
        device.is_advertisement_gated = False
        device.initialize = AsyncMock()
        device.update = AsyncMock(side_effect=slow_update)
        hass = SimpleNamespace(
            data={},
            config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()),
            bus=MagicMock(),
        )
        entry = MagicMock(
            entry_id="test-entry",
            title="Timer",
            data={"address": "test-address"},
            options={},
        )

        def background(hass, coroutine, name):
            task = asyncio.create_task(coroutine)
            background_tasks.append(task)
            return task

        entry.async_create_background_task.side_effect = background
        advertisement = SimpleNamespace(device=object(), advertisement=object())
        with (
            patch.object(
                integration.bluetooth,
                "async_last_service_info",
                return_value=advertisement,
            ),
            patch.object(integration.bluetooth, "async_register_callback"),
            patch.object(integration, "HASSTuyaBLEDeviceManager"),
            patch.object(integration, "TuyaBLEDevice", return_value=device),
            patch.object(integration, "TuyaBLECoordinator"),
            patch.object(integration, "get_device_product_info"),
        ):
            setup = asyncio.create_task(integration.async_setup_entry(hass, entry))
            try:
                await asyncio.wait_for(started.wait(), 1)
                # These yields are a heartbeat: they still run while BLE waits.
                for _ in range(10):
                    await asyncio.sleep(0)
                self.assertTrue(
                    setup.done(),
                    "Integration setup is still waiting for the Bluetooth status request",
                )
                self.assertEqual(
                    hass.config_entries.async_forward_entry_setups.await_count, 1
                )
            finally:
                release.set()
                await setup
                if background_tasks:
                    await asyncio.gather(*background_tasks)

    async def test_unload_cancels_refresh_before_waiting_for_disconnect(self):
        cancelled = asyncio.Event()

        async def stop():
            self.assertTrue(
                cancelled.is_set(),
                "Unload must cancel the refresh before waiting for its connection lock",
            )

        data = SimpleNamespace(
            device=SimpleNamespace(stop=AsyncMock(side_effect=stop)),
            cancel_status_updates=cancelled.set,
        )
        hass = SimpleNamespace(
            data={integration.DOMAIN: {"test-entry": data}},
            config_entries=SimpleNamespace(
                async_unload_platforms=AsyncMock(return_value=True)
            ),
        )
        entry = SimpleNamespace(entry_id="test-entry")
        self.assertTrue(await integration.async_unload_entry(hass, entry))


if __name__ == "__main__":
    unittest.main()
