"""Action and confirmation tests; no real Bluetooth device is contacted."""

import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.tuya_local_ble.schedule_sensor import WateringScheduleSensor
from custom_components.tuya_local_ble.tuya_ble.const import TuyaBLECode
from custom_components.tuya_local_ble.tuya_ble.tuya_ble import TuyaBLEDevice


class ScheduleActionTests(unittest.IsolatedAsyncioTestCase):
    def make_sensor(
        self, dp_id=102, raw="0000001204f6054b000300070001021204f6054b0003000700"
    ):
        self.device = SimpleNamespace(
            device_id="test-device",
            datapoints={dp_id: SimpleNamespace(value=bytes.fromhex(raw))},
            async_send_raw_command=AsyncMock(),
        )
        data = SimpleNamespace(
            device=self.device, coordinator=MagicMock(), product=MagicMock()
        )
        with patch(
            "custom_components.tuya_local_ble.devices.get_device_info",
            return_value=None,
        ):
            entity = WateringScheduleSensor(MagicMock(), data, dp_id)
        entity.async_write_ha_state = MagicMock()
        return entity

    def report(self, entity, raw):
        entity._receive_reports(
            [SimpleNamespace(id=entity._dp_id, value=bytes.fromhex(raw))]
        )

    async def test_create_waits_for_new_record_and_accepts_normalized_byte(self):
        entity = self.make_sensor(raw="00")
        task = asyncio.create_task(
            entity.async_set_cyclic_schedule(
                outlet=1,
                start_time="21:10",
                end_time="22:35",
                duration=3,
                interval=7,
                weekdays=["mon", "thu"],
            )
        )
        await asyncio.sleep(0)
        self.device.async_send_raw_command.assert_awaited_once_with(
            102, bytes.fromhex("0003011204f6054b0003000764")
        )
        self.assertEqual(entity.native_value, 0)
        self.report(entity, "00")
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        self.report(entity, "0000011204f6054b0003000700")
        await task
        self.assertEqual(entity.native_value, 1)

    async def test_delete_preserves_other_record(self):
        entity = self.make_sensor()
        task = asyncio.create_task(entity.async_delete_schedule(0))
        await asyncio.sleep(0)
        self.device.async_send_raw_command.assert_awaited_once_with(
            102, bytes.fromhex("000400")
        )
        self.report(entity, "0001021204f6054b0003000700")
        await task
        self.assertEqual(entity.extra_state_attributes["schedules"][0]["id"], 1)

    async def test_edit_and_enable_preserve_report_fields(self):
        entity = self.make_sensor()
        task = asyncio.create_task(
            entity.async_set_cyclic_schedule(
                schedule_id=0,
                outlet=1,
                start_time="21:20",
                end_time="22:45",
                duration=4,
                interval=9,
                weekdays=["tue", "sat"],
                enabled=False,
            )
        )
        await asyncio.sleep(0)
        self.device.async_send_raw_command.assert_awaited_once_with(
            102, bytes.fromhex("0002000044050005550004000900")
        )
        self.report(entity, "0000004405000555000400090001021204f6054b0003000700")
        await task
        task = asyncio.create_task(entity.async_set_schedule_enabled(0, True))
        await asyncio.sleep(0)
        self.report(entity, "0000014405000555000400090001021204f6054b0003000700")
        await task
        self.assertTrue(entity.extra_state_attributes["schedules"][0]["enabled"])

    async def test_reject_unknown_id_wrong_sensor_and_missing_report(self):
        entity = self.make_sensor()
        with self.assertRaises(ServiceValidationError):
            await entity.async_delete_schedule(99)
        with self.assertRaises(ServiceValidationError):
            await entity.async_set_normal_schedule()
        entity._records = None
        with self.assertRaises(ServiceValidationError):
            await entity.async_delete_schedule(0)
        self.device.async_send_raw_command.assert_not_awaited()

    async def test_timeout_keeps_confirmed_state(self):
        entity = self.make_sensor()

        async def fail(*args):
            raise TimeoutError

        self.device.async_send_raw_command.side_effect = fail
        with self.assertRaises(HomeAssistantError):
            await entity.async_delete_schedule(0)
        self.assertEqual(entity.native_value, 2)
        self.assertIsNone(entity._report_event)

    async def test_malformed_report_does_not_replace_state(self):
        entity = self.make_sensor()
        self.report(entity, "0001")
        self.assertEqual(entity.native_value, 2)

    async def test_raw_command_does_not_mutate_report_cache(self):
        transport = SimpleNamespace(
            _ensure_connected=AsyncMock(), _protocol_version=3, _send_packet=AsyncMock()
        )
        await TuyaBLEDevice.async_send_raw_command(
            transport, 102, bytes.fromhex("000400")
        )
        transport._send_packet.assert_awaited_once_with(
            TuyaBLECode.FUN_SENDER_DPS, bytes.fromhex("660003000400"), False
        )

    async def test_real_homeassistant_action_routing(self):
        import tempfile

        from homeassistant.core import HomeAssistant
        from homeassistant.helpers.entity_platform import EntityPlatform

        from custom_components.tuya_local_ble.schedule_sensor import register_services

        with tempfile.TemporaryDirectory() as config_dir:
            hass = HomeAssistant(config_dir)
            entity = self.make_sensor()
            entity.hass = hass
            entity.entity_id = "sensor.test_cycles"
            self.device.is_advertisement_gated = False
            entity.async_set_schedule_enabled = AsyncMock()
            platform = EntityPlatform.__new__(EntityPlatform)
            platform.hass = hass
            platform.platform_data = SimpleNamespace(platform_name="tuya_local_ble")
            platform.domain_platform_entities = {entity.entity_id: entity}
            with patch(
                "custom_components.tuya_local_ble.schedule_sensor.entity_platform.async_get_current_platform",
                return_value=platform,
            ):
                register_services()
            try:
                await hass.services.async_call(
                    "tuya_local_ble",
                    "set_schedule_enabled",
                    {
                        "entity_id": entity.entity_id,
                        "schedule_id": 0,
                        "enabled": True,
                    },
                    blocking=True,
                )
                entity.async_set_schedule_enabled.assert_awaited_once_with(
                    schedule_id=0, enabled=True
                )
            finally:
                await hass.async_stop()

    async def test_weather_delay_default_migration_respects_user_choice(self):
        from homeassistant.helpers.entity_registry import RegistryEntryDisabler

        from custom_components.tuya_local_ble import select
        from custom_components.tuya_local_ble.const import DOMAIN

        registry = MagicMock()
        registry.async_get_entity_id.side_effect = ["select.delay1", "select.delay2"]
        registry.async_get.side_effect = [
            SimpleNamespace(disabled_by=RegistryEntryDisabler.INTEGRATION),
            SimpleNamespace(disabled_by=RegistryEntryDisabler.USER),
        ]
        device = MagicMock(category="ggq", product_id="qycalacn", device_id="test")
        entry = SimpleNamespace(entry_id="test-entry")
        data = SimpleNamespace(
            device=device, coordinator=MagicMock(), product=MagicMock()
        )
        hass = SimpleNamespace(data={DOMAIN: {entry.entry_id: data}})
        with patch.object(select.er, "async_get", return_value=registry):
            await select.async_setup_entry(hass, entry, MagicMock())
        registry.async_update_entity.assert_called_once_with(
            "select.delay1", disabled_by=None
        )
        for mapping in select.get_mapping_by_device(device):
            self.assertTrue(mapping.description.entity_registry_enabled_default)
            self.assertEqual(
                mapping.description.options, ["off", "1", "2", "3", "4", "5", "6", "7"]
            )

    async def test_action_schemas_accept_ui_values(self):
        import voluptuous as vol

        from custom_components.tuya_local_ble.schedule_sensor import register_services

        platform = MagicMock()
        with patch(
            "custom_components.tuya_local_ble.schedule_sensor.entity_platform.async_get_current_platform",
            return_value=platform,
        ):
            register_services()
        registered = {
            args[0]: args[1]
            for args, kwargs in platform.async_register_entity_service.call_args_list
        }
        fields = vol.Schema(registered["set_cyclic_schedule"])(
            {
                "outlet": "1",
                "start_time": "21:10:00",
                "end_time": "22:35:00",
                "duration": 3.0,
                "interval": 7.0,
                "weekdays": ["mon", "thu"],
            }
        )
        self.assertEqual(fields["outlet"], 1)
        self.assertTrue(fields["enabled"])
        import yaml
        from homeassistant.helpers.selector import validate_selector

        metadata = yaml.safe_load(
            (
                Path(__file__).parents[1]
                / "custom_components/tuya_local_ble/services.yaml"
            ).read_text()
        )
        for action in metadata.values():
            for field in action["fields"].values():
                validate_selector(field["selector"])


if __name__ == "__main__":
    unittest.main()
