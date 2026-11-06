"""Manage-schedules options forms, using HA selectors and fake device actions."""

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, PropertyMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.tuya_local_ble.config_flow import TuyaBLEOptionsFlow
from custom_components.tuya_local_ble.const import DOMAIN
from custom_components.tuya_local_ble.watering_schedule import describe, parse_report


class ScheduleFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        self.entry = SimpleNamespace(
            entry_id="timer-entry",
            options={
                "category": "ggq",
                "product_id": "qycalacn",
                "keep_connected": True,
                "device_name": "Test timer",
            },
        )
        self.flow = TuyaBLEOptionsFlow()
        self.flow.hass = self.hass
        self.flow.flow_id = "test-flow"
        self.property = patch.object(
            TuyaBLEOptionsFlow,
            "config_entry",
            new_callable=PropertyMock,
            return_value=self.entry,
        )
        self.property.start()
        self.hass.data[DOMAIN] = {
            self.entry.entry_id: SimpleNamespace(
                device=SimpleNamespace(device_id="test-timer")
            )
        }
        dr.async_setup(self.hass)
        await dr.async_load(self.hass, load_empty=True)
        await er.async_load(self.hass, load_empty=True)
        self.registry = er.async_get(self.hass)
        self.entities = {}
        for dp_id, key, raw in [
            (101, "normal_schedules", "000104b0000900644007ea0b020301"),
            (
                102,
                "cyclic_schedules",
                "0000001204f6054b000300070001021204f6054b0003000700",
            ),
        ]:
            registered = self.registry.async_get_or_create(
                "sensor", DOMAIN, f"test-timer-{key}", suggested_object_id=key
            )
            self.entities[dp_id] = registered.entity_id
            schedules = [
                describe(dp_id, record)
                for record in parse_report(dp_id, bytes.fromhex(raw))
            ]
            self.hass.states.async_set(
                registered.entity_id, str(len(schedules)), {"schedules": schedules}
            )
        self.call = patch.object(
            type(self.hass.services), "async_call", new_callable=AsyncMock
        )
        self.service = self.call.start()

    async def asyncTearDown(self):
        self.call.stop()
        self.property.stop()
        await self.hass.async_stop()
        self.directory.cleanup()

    async def test_entry_menu_and_live_list_do_not_write(self):
        result = await self.flow.async_step_init()
        self.assertEqual(
            result["menu_options"], ["manage_schedules", "connection_options"]
        )
        result = await self.flow.async_step_manage_schedules()
        options = (
            result["data_schema"]
            .schema[next(iter(result["data_schema"].schema))]
            .config["options"]
        )
        labels = [option["label"] for option in options]
        self.assertTrue(
            any(
                "Valve 2 - Normal #1" in label and "Every 3 days" in label
                for label in labels
            )
        )
        self.assertTrue(
            any(
                "Valve 1 - Cyclic #0" in label and "Disabled" in label
                for label in labels
            )
        )
        self.service.assert_not_awaited()

    async def test_edit_prefills_and_retains_disabled_state(self):
        result = await self.flow.async_step_manage_schedules({"schedule": "101:1"})
        self.assertEqual(result["step_id"], "normal_schedule")
        self.assertTrue(result["last_step"])
        schema = result["data_schema"]
        defaults = {key.schema: key.default() for key in schema.schema}
        self.assertEqual(defaults["outlet"], "2")
        self.assertEqual(defaults["start_time"], "20:00")
        self.assertEqual(defaults["duration"], 9)
        self.assertFalse(defaults["enabled"])
        self.assertEqual(defaults["interval_days"], 3)
        defaults["duration"] = 10
        result = await self.flow.async_step_normal_schedule(schema(defaults))
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"], self.entry.options)
        self.service.assert_awaited_once_with(
            DOMAIN,
            "set_normal_schedule",
            {
                "outlet": 2,
                "start_time": "20:00",
                "duration": 10,
                "enabled": False,
                "recurrence": "interval",
                "start_date": "2026-11-02",
                "interval_days": 3,
                "schedule_id": 1,
                "entity_id": self.entities[101],
            },
            blocking=True,
        )

    async def test_cyclic_edit_sends_only_matching_fields(self):
        result = await self.flow.async_step_manage_schedules({"schedule": "102:0"})
        self.assertEqual(result["step_id"], "cyclic_schedule")
        defaults = {key.schema: key.default() for key in result["data_schema"].schema}
        self.assertEqual(defaults["weekdays"], ["mon", "thu"])
        await self.flow.async_step_cyclic_schedule(result["data_schema"](defaults))
        fields = self.service.call_args.args[2]
        self.assertEqual(fields["schedule_id"], 0)
        self.assertEqual(fields["entity_id"], self.entities[102])
        self.assertFalse(fields["enabled"])
        self.assertNotIn("recurrence", fields)

    async def test_create_omits_id_and_ignores_irrelevant_weekly_fields(self):
        result = await self.flow.async_step_manage_schedules({"schedule": "add_normal"})
        fields = {key.schema: key.default() for key in result["data_schema"].schema}
        fields.update(recurrence="weekly", weekdays=["sat"])
        await self.flow.async_step_normal_schedule(result["data_schema"](fields))
        sent = self.service.call_args.args[2]
        self.assertNotIn("schedule_id", sent)
        self.assertNotIn("start_date", sent)
        self.assertNotIn("interval_days", sent)
        self.assertTrue(sent["enabled"])

    async def test_delete_toggle_sends_only_delete_and_completes_flow(self):
        result = await self.flow.async_step_manage_schedules({"schedule": "102:1"})
        fields = {key.schema: key.default() for key in result["data_schema"].schema}
        self.assertFalse(fields["delete"])
        self.service.assert_not_awaited()
        fields["delete"] = True
        # Deletion ignores schedule edits and their device-specific validation.
        fields["end_time"] = "00:00"
        result = await self.flow.async_step_cyclic_schedule(
            result["data_schema"](fields)
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"], self.entry.options)
        self.service.assert_awaited_once_with(
            DOMAIN,
            "delete_schedule",
            {"schedule_id": 1, "entity_id": self.entities[102]},
            blocking=True,
        )

    async def test_enabled_toggle_is_saved_with_schedule(self):
        result = await self.flow.async_step_manage_schedules({"schedule": "102:1"})
        fields = {key.schema: key.default() for key in result["data_schema"].schema}
        self.assertFalse(fields["enabled"])
        fields["enabled"] = True
        result = await self.flow.async_step_cyclic_schedule(
            result["data_schema"](fields)
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(self.service.call_args.args[1], "set_cyclic_schedule")
        sent = self.service.call_args.args[2]
        self.assertTrue(sent["enabled"])
        self.assertEqual(sent["schedule_id"], 1)
        self.assertNotIn("delete", sent)

    async def test_failed_save_preserves_submitted_values(self):
        await self.flow.async_step_manage_schedules({"schedule": "102:0"})
        self.service.side_effect = HomeAssistantError("Timer did not confirm")
        fields = {
            "outlet": "1",
            "start_time": "21:20",
            "end_time": "22:35",
            "duration": 4,
            "interval": 9,
            "enabled": False,
            "weekdays": ["tue"],
        }
        result = await self.flow.async_step_cyclic_schedule(fields)
        self.assertEqual(result["errors"], {"base": "schedule_change_failed"})
        self.assertIn(
            "Timer did not confirm", result["description_placeholders"]["error"]
        )
        defaults = {key.schema: key.default() for key in result["data_schema"].schema}
        self.assertEqual(defaults["duration"], 4)
        self.assertEqual(defaults["weekdays"], ["tue"])

    async def test_unavailable_and_deleted_entries_never_write(self):
        self.hass.states.async_set(self.entities[101], "unavailable")
        result = await self.flow.async_step_manage_schedules()
        self.assertIn("unavailable", result["description_placeholders"]["warning"])
        await self.flow.async_step_manage_schedules({"schedule": "102:0"})
        self.hass.states.async_set(self.entities[102], "0", {"schedules": []})
        result = await self.flow.async_step_schedule_form()
        self.assertEqual(result["reason"], "schedule_unavailable")
        self.service.assert_not_awaited()

    async def test_picker_has_no_done_option(self):
        result = await self.flow.async_step_manage_schedules()
        picker = next(iter(result["data_schema"].schema.values()))
        self.assertNotIn(
            "done", [option["value"] for option in picker.config["options"]]
        )
        self.service.assert_not_awaited()

    async def test_create_form_has_no_delete_toggle(self):
        result = await self.flow.async_step_manage_schedules({"schedule": "add_cyclic"})
        self.assertNotIn("delete", [key.schema for key in result["data_schema"].schema])

    async def test_failed_delete_preserves_toggle_and_edits(self):
        result = await self.flow.async_step_manage_schedules({"schedule": "102:0"})
        fields = {key.schema: key.default() for key in result["data_schema"].schema}
        fields.update(delete=True, duration=12)
        self.service.side_effect = HomeAssistantError("Timer did not confirm")
        result = await self.flow.async_step_cyclic_schedule(
            result["data_schema"](fields)
        )
        self.assertEqual(result["errors"], {"base": "schedule_change_failed"})
        defaults = {key.schema: key.default() for key in result["data_schema"].schema}
        self.assertTrue(defaults["delete"])
        self.assertEqual(defaults["duration"], 12)
        self.assertEqual(self.service.call_args.args[1], "delete_schedule")

    async def test_connection_settings_preserve_existing_options(self):
        result = await self.flow.async_step_connection_options(
            {"keep_connected": False}
        )
        self.assertEqual(
            result["data"], {**self.entry.options, "keep_connected": False}
        )

    async def test_loaded_product_metadata_enables_schedule_menu(self):
        self.entry.options = {"keep_connected": True}
        device = self.hass.data[DOMAIN][self.entry.entry_id].device
        device.category = "ggq"
        device.product_id = "qycalacn"
        result = await self.flow.async_step_init()
        self.assertIn("manage_schedules", result["menu_options"])

    async def test_bluetooth_failure_is_shown_in_the_form(self):
        from bleak import BleakError

        result = await self.flow.async_step_manage_schedules({"schedule": "102:0"})
        fields = {key.schema: key.default() for key in result["data_schema"].schema}
        self.service.side_effect = BleakError("Device disconnected")
        result = await self.flow.async_step_cyclic_schedule(
            result["data_schema"](fields)
        )
        self.assertEqual(result["errors"], {"base": "schedule_change_failed"})
        self.assertIn(
            "Could not communicate", result["description_placeholders"]["error"]
        )

    async def test_other_products_keep_connection_form(self):
        self.entry.options = {"product_id": "other-product"}
        result = await self.flow.async_step_init()
        self.assertEqual(result["step_id"], "connection_options")


if __name__ == "__main__":
    unittest.main()
