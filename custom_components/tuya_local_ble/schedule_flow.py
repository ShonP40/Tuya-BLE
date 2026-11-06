"""Home Assistant options forms for schedules stored on the tap timer."""

from __future__ import annotations

import voluptuous as vol
from bleak import BleakError
from homeassistant.config_entries import OptionsFlow
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .tuya_ble.exceptions import TuyaBLEError
from .watering_schedule import CYCLIC_DP, NORMAL_DP, WEEKDAYS

DAY_NAMES = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)
REPEAT_NAMES = {
    "weekly": "Selected weekdays",
    "odd_days": "Odd-numbered days",
    "even_days": "Even-numbered days",
    "interval": "Every X days",
}


def select_options(options, *, multiple=False):
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[{"value": key, "label": label} for key, label in options.items()],
            multiple=multiple,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def number(maximum):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=maximum,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def summary(schedule, cyclic=False):
    """Make the picker useful without inspecting entity attributes."""
    if cyclic:
        timing = f"{schedule['start_time']}-{schedule['end_time']}, {schedule['duration']} min / {schedule['interval']} min interval"
        repeat = ", ".join(day.title() for day in schedule["weekdays"])
    else:
        timing = f"{schedule['start_time']}, {schedule['duration']} min"
        recurrence = schedule["recurrence"]
        repeat = (
            ", ".join(day.title() for day in schedule["weekdays"])
            if recurrence == "weekly"
            else f"Every {schedule['interval_days']} days from {schedule['start_date']}"
            if recurrence == "interval"
            else REPEAT_NAMES.get(recurrence, recurrence)
        )
    return (
        f"Valve {schedule['outlet']} - {'Cyclic' if cyclic else 'Normal'} #{schedule['id']}"
        f" - {timing} - {repeat} - {'Enabled' if schedule['enabled'] else 'Disabled'}"
    )


class ScheduleOptionsFlow(OptionsFlow):
    """Manage schedules through existing entity actions and confirmed state."""

    def __init__(self):
        super().__init__()
        self._schedule_dp = NORMAL_DP
        self._schedule_id = None

    def _schedule_entity(self, dp_id):
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if data is None:
            raise HomeAssistantError(
                "The integration must be loaded to manage schedules."
            )
        key = "normal_schedules" if dp_id == NORMAL_DP else "cyclic_schedules"
        entity_id = er.async_get(self.hass).async_get_entity_id(
            "sensor", DOMAIN, f"{data.device.device_id}-{key}"
        )
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            raise HomeAssistantError(
                "Schedule sensor is unavailable. Enable it and wait for the timer to connect and report its schedules."
            )
        schedules = state.attributes.get("schedules")
        if schedules is None:
            raise HomeAssistantError(
                "Schedules have not been received from the timer yet."
            )
        return entity_id, schedules

    def _selected_schedule(self):
        _, schedules = self._schedule_entity(self._schedule_dp)
        for schedule in schedules:
            if schedule["id"] == self._schedule_id:
                return schedule
        raise HomeAssistantError(
            "This schedule no longer exists. Close Configure and reopen the schedule list."
        )

    async def _schedule_action(self, service, fields):
        entity_id, _ = self._schedule_entity(self._schedule_dp)
        if self._schedule_id is not None:
            # Refresh before writing so a removed entry cannot become a create.
            self._selected_schedule()
            fields = {**fields, "schedule_id": self._schedule_id}
        try:
            await self.hass.services.async_call(
                DOMAIN,
                service,
                {**fields, "entity_id": entity_id},
                blocking=True,
            )
        except (TuyaBLEError, BleakError, OSError) as err:
            raise HomeAssistantError(
                "Could not communicate with the timer. Check the connection and "
                "reported schedules before retrying."
            ) from err

    async def async_step_manage_schedules(self, user_input=None):
        """List live schedules from both valves and both schedule types."""
        if user_input is not None:
            choice = user_input["schedule"]
            if choice in ("add_normal", "add_cyclic"):
                self._schedule_dp = NORMAL_DP if choice == "add_normal" else CYCLIC_DP
                self._schedule_id = None
                return await self.async_step_schedule_form()
            self._schedule_dp, self._schedule_id = map(int, choice.split(":"))
            return await self.async_step_schedule_form()

        options = {}
        warnings = []
        for dp_id in (NORMAL_DP, CYCLIC_DP):
            try:
                _, schedules = self._schedule_entity(dp_id)
            except HomeAssistantError as err:
                warnings.append(str(err))
                continue
            for schedule in schedules:
                options[f"{dp_id}:{schedule['id']}"] = summary(
                    schedule, dp_id == CYCLIC_DP
                )
            options["add_normal" if dp_id == NORMAL_DP else "add_cyclic"] = (
                "Add normal schedule" if dp_id == NORMAL_DP else "Add cyclic schedule"
            )
        return self.async_show_form(
            step_id="manage_schedules",
            data_schema=vol.Schema({vol.Required("schedule"): select_options(options)}),
            description_placeholders={
                "warning": " ".join(dict.fromkeys(warnings)),
            },
        )

    async def async_step_schedule_form(self, user_input=None):
        """Prefill existing values; save through the same validated action path."""
        cyclic = self._schedule_dp == CYCLIC_DP
        errors = {}
        error_detail = ""
        defaults = {
            "outlet": 1,
            "start_time": "07:00",
            "duration": 5,
            "enabled": True,
            "recurrence": "weekly",
            "weekdays": [],
            "start_date": dt_util.now().date().isoformat(),
            "interval_days": 1,
            "end_time": "08:00",
            "interval": 7,
        }
        try:
            if self._schedule_id is not None:
                defaults.update(self._selected_schedule())
                if not cyclic and defaults["recurrence"] not in REPEAT_NAMES:
                    return self.async_abort(reason="unsupported_schedule")
            else:
                self._schedule_entity(self._schedule_dp)
        except HomeAssistantError:
            return self.async_abort(reason="schedule_unavailable")
        if user_input is not None:
            defaults.update(user_input)
            fields = dict(user_input)
            delete = fields.pop("delete", False)
            if delete:
                try:
                    if self._schedule_id is None:
                        raise HomeAssistantError("A new schedule cannot be deleted.")
                    await self._schedule_action("delete_schedule", {})
                except HomeAssistantError as err:
                    errors["base"] = "schedule_change_failed"
                    error_detail = str(err)
                else:
                    return self._finish_schedule_change()
            else:
                fields["outlet"] = int(fields["outlet"])
                for key in ("duration", "interval", "interval_days"):
                    if key in fields:
                        fields[key] = int(fields[key])
                if not cyclic:
                    recurrence = fields["recurrence"]
                    if recurrence != "weekly":
                        fields.pop("weekdays", None)
                    if recurrence != "interval":
                        fields.pop("interval_days", None)
                        # Preserve the existing date outside interval recurrence.
                        fields.pop("start_date", None)
                    elif "start_date" not in fields:
                        errors["start_date"] = "start_date_required"
                if not errors:
                    try:
                        await self._schedule_action(
                            "set_cyclic_schedule" if cyclic else "set_normal_schedule",
                            fields,
                        )
                    except (HomeAssistantError, ValueError) as err:
                        errors["base"] = "schedule_change_failed"
                        error_detail = str(err)
                    else:
                        return self._finish_schedule_change()
        schema = {
            vol.Required(
                "enabled", default=defaults["enabled"]
            ): selector.BooleanSelector(),
            vol.Required("outlet", default=str(defaults["outlet"])): select_options(
                {"1": "Valve 1", "2": "Valve 2"}
            ),
            vol.Required(
                "start_time", default=defaults["start_time"]
            ): selector.TimeSelector(),
        }
        days = select_options(dict(zip(WEEKDAYS, DAY_NAMES)), multiple=True)
        if cyclic:
            schema.update(
                {
                    vol.Required(
                        "end_time", default=defaults["end_time"]
                    ): selector.TimeSelector(),
                    vol.Required("weekdays", default=defaults["weekdays"]): days,
                    vol.Required("duration", default=defaults["duration"]): number(
                        1440
                    ),
                    vol.Required("interval", default=defaults["interval"]): number(
                        1440
                    ),
                }
            )
        else:
            schema.update(
                {
                    vol.Required("duration", default=defaults["duration"]): number(
                        1440
                    ),
                    vol.Required(
                        "recurrence", default=defaults["recurrence"]
                    ): select_options(REPEAT_NAMES),
                    vol.Optional("weekdays", default=defaults["weekdays"]): days,
                    vol.Optional(
                        "start_date", default=defaults["start_date"]
                    ): selector.DateSelector(),
                    vol.Optional(
                        "interval_days", default=defaults["interval_days"]
                    ): number(255),
                }
            )
        if self._schedule_id is not None:
            schema[vol.Optional("delete", default=defaults.get("delete", False))] = (
                selector.BooleanSelector()
            )
        return self.async_show_form(
            step_id="cyclic_schedule" if cyclic else "normal_schedule",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={"error": error_detail},
            last_step=True,
        )

    # Form step IDs must also be resolvable on subsequent frontend submissions.
    async def async_step_normal_schedule(self, user_input=None):
        return await self.async_step_schedule_form(user_input)

    async def async_step_cyclic_schedule(self, user_input=None):
        return await self.async_step_schedule_form(user_input)

    def _finish_schedule_change(self):
        # Finish as a successful native options flow. Returning unchanged options
        # makes HA skip update listeners, so no integration reload is triggered.
        return self.async_create_entry(title="", data=dict(self.config_entry.options))
