"""Schedule state and entity actions for the Hoselink tap timer."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.util import dt as dt_util

from .devices import TuyaBLEEntity
from .watering_schedule import (
    CYCLIC_DP,
    NORMAL_DP,
    RECURRENCES,
    WEEKDAYS,
    cyclic_record,
    describe,
    normal_record,
    parse_report,
    set_enabled,
)

_LOGGER = logging.getLogger(__name__)
SCHEDULE_FEATURE = 1
ID = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
MINUTES = vol.All(vol.Coerce(int), vol.Range(min=1, max=1440))
DAYS = vol.All(cv.ensure_list, [vol.In(WEEKDAYS)])
COMMON = {
    vol.Optional("schedule_id"): ID,
    vol.Required("outlet"): vol.All(vol.Coerce(int), vol.In([1, 2])),
    vol.Required("start_time"): cv.string,
    vol.Required("duration"): MINUTES,
    vol.Optional("enabled", default=True): cv.boolean,
}


def register_services() -> None:
    """Register actions on the sensor platform; only schedule sensors support them."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_normal_schedule",
        {
            **COMMON,
            vol.Optional("recurrence", default="weekly"): vol.In(RECURRENCES),
            vol.Optional("weekdays"): DAYS,
            vol.Optional("start_date"): cv.string,
            vol.Optional("interval_days", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
        },
        "async_set_normal_schedule",
        required_features=[SCHEDULE_FEATURE],
    )
    platform.async_register_entity_service(
        "set_cyclic_schedule",
        {
            **COMMON,
            vol.Required("end_time"): cv.string,
            vol.Required("interval"): MINUTES,
            vol.Required("weekdays"): DAYS,
        },
        "async_set_cyclic_schedule",
        required_features=[SCHEDULE_FEATURE],
    )
    platform.async_register_entity_service(
        "set_schedule_enabled",
        {vol.Required("schedule_id"): ID, vol.Required("enabled"): cv.boolean},
        "async_set_schedule_enabled",
        required_features=[SCHEDULE_FEATURE],
    )
    platform.async_register_entity_service(
        "delete_schedule",
        {vol.Required("schedule_id"): ID},
        "async_delete_schedule",
        required_features=[SCHEDULE_FEATURE],
    )


class WateringScheduleSensor(TuyaBLEEntity, SensorEntity):
    """Count schedules and expose only confirmed device records as attributes."""

    _attr_supported_features = SCHEDULE_FEATURE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, hass, data, dp_id):
        key = "normal_schedules" if dp_id == NORMAL_DP else "cyclic_schedules"
        super().__init__(
            hass,
            data.coordinator,
            data.device,
            data.product,
            SensorEntityDescription(key=key),
        )
        self._dp_id = dp_id
        self._records: list[bytes] | None = None
        self._write_lock = asyncio.Lock()
        self._report_event: asyncio.Event | None = None
        self._report_predicate = None
        self._matched = False
        datapoint = self._device.datapoints[dp_id]
        if datapoint is not None:
            self._accept_report(datapoint.value)

    @property
    def native_value(self):
        return None if self._records is None else len(self._records)

    @property
    def extra_state_attributes(self):
        return {
            "schedules": None
            if self._records is None
            else [describe(self._dp_id, record) for record in self._records],
            "duration_unit": "minutes",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._device.register_callback(self._receive_reports))
        # Include reports arriving between construction and callback registration.
        datapoint = self._device.datapoints[self._dp_id]
        if datapoint is not None:
            self._accept_report(datapoint.value)

    def _accept_report(self, value):
        try:
            records = parse_report(self._dp_id, value)
        except ValueError:
            _LOGGER.warning("Ignoring malformed schedule report for DP %s", self._dp_id)
            return
        self._records = records
        if self._report_event is not None and self._report_predicate(records):
            self._matched = True
            self._report_event.set()

    @callback
    def _receive_reports(self, datapoints):
        # Decode incoming reports only, keeping command framing out of state.
        for datapoint in datapoints:
            if datapoint.id == self._dp_id:
                self._accept_report(datapoint.value)
                self.async_write_ha_state()

    def _existing(self, schedule_id):
        if self._records is None:
            raise ServiceValidationError(
                "Schedules have not been received from the timer yet"
            )
        if schedule_id is None:
            return None
        for record in self._records:
            if record[0] == schedule_id:
                return record
        raise ServiceValidationError(f"Schedule {schedule_id} does not exist")

    async def _send(self, payload, predicate):
        """Require the timer to report the requested result, not just a BLE ACK."""
        self._report_event = asyncio.Event()
        self._report_predicate = predicate
        self._matched = False
        try:
            async with asyncio.timeout(30):
                await self._device.async_send_raw_command(self._dp_id, payload)
                if not self._matched:
                    await self._report_event.wait()
        except TimeoutError as err:
            raise HomeAssistantError(
                "Timer did not confirm the schedule change. Check its reported "
                "schedules before retrying; the command may have succeeded."
            ) from err
        finally:
            self._report_event = None
            self._report_predicate = None

    async def _set_schedule(self, dp_id, schedule_id, builder, fields):
        if self._dp_id != dp_id:
            raise ServiceValidationError(
                "Select the matching normal or cyclic schedule sensor"
            )
        async with self._write_lock:
            existing = self._existing(schedule_id)
            try:
                record = builder(existing=existing, **fields)
            except (ValueError, TypeError) as err:
                raise ServiceValidationError(str(err)) from err
            if existing is None:
                size = len(record)
                if 1 + (len(self._records) + 1) * size > 128:
                    raise ServiceValidationError(
                        "Schedule list would exceed the timer's 128-byte limit"
                    )
                old_ids = {item[0] for item in self._records}
                # The timer normalizes the final cyclic create byte from 100
                # to 0. It also assigns the ID, so exclude both from matching.
                body = record[1:-1] if dp_id == CYCLIC_DP else record[1:]

                def matches(records):
                    return any(
                        item[0] not in old_ids
                        and (item[1:-1] if dp_id == CYCLIC_DP else item[1:]) == body
                        for item in records
                    )

                await self._send(b"\x00\x03" + record[1:], matches)
            else:
                await self._send(
                    b"\x00\x02" + record, lambda records: record in records
                )

    async def async_set_normal_schedule(self, schedule_id=None, **fields):
        # Use HA's configured local date, not the host's timezone, for creates.
        if (
            schedule_id is None
            and "start_date" not in fields
            and fields.get("recurrence", "weekly") != "interval"
        ):
            fields["start_date"] = dt_util.now().date().isoformat()
        await self._set_schedule(NORMAL_DP, schedule_id, normal_record, fields)

    async def async_set_cyclic_schedule(self, schedule_id=None, **fields):
        await self._set_schedule(CYCLIC_DP, schedule_id, cyclic_record, fields)

    async def async_set_schedule_enabled(self, schedule_id, enabled):
        async with self._write_lock:
            record = set_enabled(self._dp_id, self._existing(schedule_id), enabled)
            await self._send(b"\x00\x02" + record, lambda records: record in records)

    async def async_delete_schedule(self, schedule_id):
        async with self._write_lock:
            self._existing(schedule_id)
            await self._send(
                b"\x00\x04" + bytes([schedule_id]),
                lambda records: all(record[0] != schedule_id for record in records),
            )
