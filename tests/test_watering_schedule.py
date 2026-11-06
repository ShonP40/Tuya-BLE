"""Protocol regressions using credential-free captured schedule payloads."""

import importlib.util
import unittest
from pathlib import Path

# The codec is deliberately independent of HA and Bluetooth dependencies.
path = (
    Path(__file__).parents[1] / "custom_components/tuya_local_ble/watering_schedule.py"
)
spec = importlib.util.spec_from_file_location("watering_schedule", path)
codec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codec)


class ScheduleCodecTests(unittest.TestCase):
    def test_normal_weekly_capture(self):
        record = codec.normal_record(
            outlet=1,
            start_time="19:00",
            duration=5,
            weekdays=["sun", "mon", "tue", "wed", "thu"],
            start_date="2026-10-31",
        )
        self.assertEqual(
            (b"\x00\x03" + record[1:]).hex(), "0003047400051f640107ea0a1f0100"
        )
        self.assertEqual(
            codec.describe(101, record)["weekdays"], ["sun", "mon", "tue", "wed", "thu"]
        )

    def test_normal_interval_capture(self):
        record = codec.normal_record(
            outlet=2,
            start_time="20:00",
            duration=9,
            recurrence="interval",
            start_date="2026-11-02",
            interval_days=3,
            enabled=False,
            existing=bytes.fromhex("0104b0000940640007ea0a1f0101"),
        )
        self.assertEqual((b"\x00" + record).hex(), "000104b0000900644007ea0b020301")
        self.assertEqual(codec.describe(101, record)["recurrence"], "interval")

    def test_all_recurrences_and_preserve_unknown_fields(self):
        old = bytearray.fromhex("000104b0000900644007ea0b020301")
        # The leading report byte is not part of a record.
        old = old[1:]
        old[6] = 37
        old[7] |= 0x0A
        for mode, flag in codec.RECURRENCES.items():
            record = codec.normal_record(
                outlet=2,
                start_time="20:00",
                duration=9,
                recurrence=mode,
                weekdays=["sat"] if mode == "weekly" else None,
                start_date="2026-11-02",
                existing=bytes(old),
            )
            self.assertEqual(record[6], 37)
            self.assertEqual(record[7], flag | 0x0B)
            self.assertEqual(codec.set_enabled(101, record, False)[7], flag | 0x0A)

    def test_cyclic_create_and_toggle_captures(self):
        for outlet, flag in [(1, 1), (2, 3)]:
            record = codec.cyclic_record(
                outlet=outlet,
                start_time="21:10",
                end_time="22:35",
                duration=3,
                interval=7,
                weekdays=["mon", "thu"],
            )
            self.assertEqual(record[1], flag)
            self.assertEqual(record[2:].hex(), "1204f6054b0003000764")
            reported = record[:-1] + b"\x00"
            toggled = codec.set_enabled(102, reported, False)
            self.assertEqual(toggled[1], flag - 1)
            self.assertEqual(toggled[2:], reported[2:])

    def test_cyclic_edits_and_multi_record_report(self):
        value = bytes.fromhex("0000014405000555000400090001021204f6054b0003000700")
        records = codec.parse_report(102, value)
        first = codec.cyclic_record(
            outlet=1,
            start_time="21:20",
            end_time="22:45",
            duration=4,
            interval=9,
            weekdays=["tue", "sat"],
            existing=records[0],
        )
        self.assertEqual(first, records[0])
        self.assertEqual(
            codec.describe(102, first),
            {
                "id": 0,
                "outlet": 1,
                "enabled": True,
                "start_time": "21:20",
                "end_time": "22:45",
                "duration": 4,
                "interval": 9,
                "weekdays": ["tue", "sat"],
            },
        )
        remaining = codec.parse_report(102, bytes.fromhex("0001021204f6054b0003000700"))
        self.assertEqual(remaining, [records[1]])
        self.assertEqual(codec.parse_report(102, b"\x00"), [])

    def test_invalid_reports(self):
        for value in [b"", b"\x01", b"\x00\x01", b"\x00" + bytes(24), bytes(129)]:
            with self.assertRaises(ValueError):
                codec.parse_report(102, value)

    def test_invalid_inputs(self):
        default = {
            "outlet": 1,
            "start_time": "21:10",
            "end_time": "22:35",
            "duration": 3,
            "interval": 7,
            "weekdays": ["mon"],
        }
        for change in [
            {"outlet": 3},
            {"duration": 0},
            {"interval": -1},
            {"end_time": "20:00"},
            {"weekdays": []},
            {"weekdays": ["bad"]},
            {"start_time": "21:10:30"},
        ]:
            with self.assertRaises(ValueError):
                codec.cyclic_record(**(default | change))
        with self.assertRaises(ValueError):
            codec.normal_record(
                outlet=1, start_time="19:00", duration=5, recurrence="interval"
            )


if __name__ == "__main__":
    unittest.main()
