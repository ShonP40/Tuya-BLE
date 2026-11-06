# Hoselink Tap Timer → Local Home Assistant Control

## Goal

Get the Hoselink dual-outlet Bluetooth tap timer off the Tuya **cloud**
integration (unreliable, requires periodic re-authentication) and onto a
**local** control path in Home Assistant.

## Hardware & Tuya identifiers

- **Timer:** Hoselink dual-outlet Bluetooth tap timer.
  - `product_id`: `qycalacn`
  - `category`: `ggq` (Tuya irrigation / valve-controller class)
  - Bluetooth-only — no WiFi radio, no LAN presence of its own.
- **Gateway:** Hoselink WiFi Gateway — the only device with a LAN IP.
  Bridges the timer's BLE to WiFi/cloud.

## Key finding: the gateway is a dumb passthrough

The gateway's data model exposes **only** two datapoints:

- DP 1 `up_channel` (raw, 128 B, read-only)
- DP 2 `down_channel` (raw, 128 B, write-only)

It does **not** re-expose the timer's datapoints addressably over the LAN.
The timer's real DPs are tunnelled as encoded BLE payloads inside those raw
frames. This is the classic pattern behind "connection succeeded but no
datapoints found" when adding a Tuya BLE sub-device through a hub.

## Timer datapoint model (from Query Things Data Model)

| DP  | Code                | Type                     | RW | Intended HA entity |
|-----|---------------------|--------------------------|----|--------------------|
| 105 | switch_1            | bool                     | rw | switch (outlet 1)  |
| 104 | switch_2            | bool                     | rw | switch (outlet 2)  |
| 106 | countdown_1         | value 0–1440 min         | rw | number             |
| 103 | countdown_2         | value 0–1440 min         | rw | number             |
| 11  | battery_percentage  | value 0–100 %            | ro | sensor             |
| 111 | use_time_1          | value 0–86400 s          | ro | sensor             |
| 110 | use_time_2          | value 0–86400 s          | ro | sensor             |
| 112 | status_1            | enum manual/auto/idle    | ro | sensor             |
| 113 | status_2            | enum manual/auto/idle    | ro | sensor             |
| 117 | weather_delay       | enum OFF/1–7             | rw | select (delay in days) |
| 114 | weather_delay2      | enum OFF/1–7             | rw | select (delay in days) |
| 19  | fault               | bitmap (len 2)           | ro | binary_sensor      |
| 101 | normal_timer        | raw 128 B                | rw | normal schedules sensor + actions  |
| 102 | cycle_timer         | raw 128 B                | rw | cyclic schedules sensor + actions     |

Both outlets have independent switches, countdowns, status and usage sensors.
Countdowns are in minutes and close an open outlet on expiry; they do not open a
closed outlet. Manual switching and countdown shutoff were tested successfully
with weather delay set to one day.

### Watering schedules

Normal and cyclic schedules are stored and executed by the timer. This integration
exposes two sensors, **Normal schedules** and **Cyclic schedules**. Their state is
the number of schedules; the `schedules` attribute lists each entry's ID, outlet,
enabled flag, and settings. `Unknown` means no valid schedule report has arrived,
not an empty schedule list. IDs are scoped to the schedule type, shared between
outlets, and are not renumbered when another entry is deleted.

To manage schedules with prefilled forms, go to **Settings > Devices & services >
Tuya Local BLE > Configure > Manage schedules**. The list includes both valves,
normal and cyclic entries, their timing/repeat settings, and enabled state.
Select an existing entry to open its prefilled edit form directly. Use the
**Enabled** toggle to enable or disable it. Select **Add normal schedule** or
**Add cyclic schedule** to create one.

Press **Submit** to send the settings to the timer and complete the flow. To delete
an existing entry, enable **Delete this schedule**, then press **Submit**. Deletion
ignores other edits in the form. The flow completes only after the timer confirms
the save or deletion. Close the dialog with **X** at any time before submitting to
exit without sending changes.

Editing prefills the current settings and retains the enabled state shown in the
form. For normal schedules, weekdays apply only to **Selected weekdays**, while
the first date and interval in days apply only to **Every X days**. All durations
and cyclic intervals are minutes. Changes wait for confirmation from the timer;
if a save fails, your entered values remain in the form. Check the reported list
before retrying a create after a timeout. Schedule management does not reload the
integration or alter connection settings. Both schedule sensors must be enabled
and have received device data to manage both schedule types.

For automations or direct action calls, in **Developer tools > Actions**, choose
one of these Tuya Local BLE actions and
target the corresponding schedule sensor:

- **Set normal watering schedule**: create a schedule, or replace one by supplying
  its `schedule_id`. Supports selected weekdays, odd-numbered days, even-numbered
  days, or every X days from a start date.
- **Set cyclic watering schedule**: create or replace repeated watering within a
  start/end window on selected weekdays.
- **Enable or disable watering schedule**: change only the enabled flag.
- **Delete watering schedule**: delete one entry by ID.

The action editor provides time, date, weekday, and numeric selectors. All
watering durations and cyclic intervals are **minutes**. Outlet numbers are 1 and
2. Times are local timer times at whole-minute resolution. Editing requires all
settings again; omit `schedule_id` only when creating a new entry. `enabled`
defaults to true, matching the app's save behavior. For interval recurrence,
`start_date` is required; `interval_days` defaults to 1. Weekly recurrence requires
at least one weekday; omit weekdays for other recurrence modes.

For example, create a weekly valve 1 schedule at 19:00 for five minutes:

```yaml
action: tuya_local_ble.set_normal_schedule
target:
  entity_id: sensor.REPLACE_WITH_NORMAL_SCHEDULES_ENTITY
data:
  outlet: 1
  start_time: "19:00"
  duration: 5
  recurrence: weekly
  weekdays: [sun, mon, tue, wed, thu]
  enabled: true
```

Create a cyclic valve 2 schedule:

```yaml
action: tuya_local_ble.set_cyclic_schedule
target:
  entity_id: sensor.REPLACE_WITH_CYCLIC_SCHEDULES_ENTITY
data:
  outlet: 2
  start_time: "21:10"
  end_time: "22:35"
  duration: 3
  interval: 7
  weekdays: [mon, thu]
  enabled: true
```

Disable or delete an entry using its reported ID:

```yaml
action: tuya_local_ble.set_schedule_enabled
target:
  entity_id: sensor.REPLACE_WITH_CYCLIC_SCHEDULES_ENTITY
data:
  schedule_id: 1
  enabled: false
```

For deletion use `tuya_local_ble.delete_schedule` with the same target and ID,
omitting `enabled`.

Writes are serialized per schedule type and wait up to 30 seconds for a matching
device report. A timeout means the outcome is uncertain; inspect the reported
schedules or the app before retrying a create to avoid duplicates. No schedules
are sent automatically at startup. Schedules must first be received from the
timer before actions can modify them. Unknown record bytes and reserved flag bits
are preserved during edits and toggles.

The action forms conservatively accept durations/intervals of 1-1440 minutes and
interval-day values of 1-255. These are integration bounds, not verified firmware
limits. Cyclic windows must end later on the same day; overnight behavior has
not been verified. The device model limits each raw schedule list to 128 bytes;
the integration prevents creates exceeding that size, but firmware may impose
additional limits. Actual schedule firing, odd/even calendar edge cases, and
whether cyclic interval means off-time or start-to-start time remain untested.

### Weather delay

Both outlets offer **Off** and **1-7 days**. The app labels Off as "Close" and
defaults its delay selection to one day. Home Assistant shows the timer's reported
value; it does not apply a one-day delay on setup. Weather delay concerns scheduled
watering; its effect on schedules still needs a live firing test. It does not
prevent manual watering or countdown shutoff in our tests.

Weather-delay entities are enabled by default again. Existing entities disabled
by the integration's previous default are re-enabled on reload; entities manually
disabled by the user retain that choice. Changing entity availability does not
change the delay stored on the timer.

### Schedule wire format

These layouts were decoded from Bluetooth app/device exchanges on this model.
No credentials or handshake data are included. Both DPs use a leading `00` byte.
Create is `00 03` plus a record without its ID; edit/toggle is `00 02` plus a
complete record; delete is `00 04 ID`. Reports are `00` followed by concatenated
records, with no operation byte.

| Normal DP 101 record offset | Bytes | Meaning |
|---|---|---|
| 0 | 1 | ID |
| 1 | 2 | Start minutes since midnight, big-endian |
| 3 | 2 | Duration minutes, big-endian |
| 5 | 1 | Weekdays, Sunday bit 0 through Saturday bit 6 |
| 6 | 1 | Unknown; observed 100, preserved on edit |
| 7 | 1 | Recurrence high nibble; enabled bit 0 |
| 8 | 2 | Start year, big-endian |
| 10 / 11 | 1 each | Start month / day |
| 12 | 1 | Interval days |
| 13 | 1 | Outlet index, 0 or 1 |

Normal recurrence values are `00` weekly, `10` odd days, `20` even days, and `40`
every X days. Add bit 0 for enabled. Disabled odd/even values are inferred from
the enabled bit; disabled weekly/interval values were captured directly.

| Cyclic DP 102 record offset | Bytes | Meaning |
|---|---|---|
| 0 | 1 | ID |
| 1 | 1 | Enabled bit 0; outlet index bit 1 |
| 2 | 1 | Weekday mask, same bit order as normal |
| 3 / 5 | 2 each | Start / end minutes since midnight, big-endian |
| 7 / 9 | 2 each | Irrigation / interval minutes, big-endian |
| 11 | 1 | Unknown; app creates with 100, timer reports 0 |

The cyclic trailing byte is preserved when editing; creates use the observed
app value 100. Its meaning is unknown. IDs are assigned by the timer, not guessed
by the integration. Empty reports (`00`) and multi-record reports were captured.

### Raw data

#### Timer Product Info

```text
"name": "Smart Dual Water  Timer",
"product_id": "qycalacn",
"product_name": "一出二水阀V2",
"category": "ggq",
```

#### Timer datapoint model

```json
{
  "result": {
    "model": "{\"modelId\":\"ej5kng\",\"services\":[{\"actions\":[],\"code\":\"\",\"description\":\"\",\"events\":[],\"name\":\"默认服务\",\"properties\":[{\"abilityId\":11,\"accessMode\":\"ro\",\"code\":\"battery_percentage\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-dp_battery\",\"attribute\":\"1024\"},\"name\":\"主电池电量\",\"typeSpec\":{\"type\":\"value\",\"max\":100,\"min\":0,\"scale\":0,\"step\":1,\"unit\":\"%\"}},{\"abilityId\":19,\"accessMode\":\"ro\",\"code\":\"fault\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-baojing\",\"scope\":\"fault\",\"attribute\":\"1024\"},\"name\":\"故障告警\",\"typeSpec\":{\"type\":\"bitmap\",\"label\":[\"1\",\"2\"],\"maxlen\":2}},{\"abilityId\":101,\"accessMode\":\"rw\",\"code\":\"normal_timer\",\"description\":\"\",\"name\":\"普通定时\",\"typeSpec\":{\"type\":\"raw\",\"maxlen\":128}},{\"abilityId\":102,\"accessMode\":\"rw\",\"code\":\"cycle_timer\",\"description\":\"\",\"name\":\"循环定时\",\"typeSpec\":{\"type\":\"raw\",\"maxlen\":128}},{\"abilityId\":103,\"accessMode\":\"rw\",\"code\":\"countdown_2\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-dp_time2\",\"attribute\":\"4096\"},\"name\":\"开关2倒计时\",\"typeSpec\":{\"type\":\"value\",\"max\":1440,\"min\":0,\"scale\":0,\"step\":1,\"unit\":\"min\"}},{\"abilityId\":104,\"accessMode\":\"rw\",\"code\":\"switch_2\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-dp_power2\",\"attribute\":\"4096\"},\"name\":\"开关2\",\"typeSpec\":{\"type\":\"bool\"}},{\"abilityId\":105,\"accessMode\":\"rw\",\"code\":\"switch_1\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-dp_power2\",\"attribute\":\"4096\"},\"name\":\"开关1\",\"typeSpec\":{\"type\":\"bool\"}},{\"abilityId\":106,\"accessMode\":\"rw\",\"code\":\"countdown_1\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-dp_time2\",\"attribute\":\"4096\"},\"name\":\"开关1倒计时\",\"typeSpec\":{\"type\":\"value\",\"max\":1440,\"min\":0,\"scale\":0,\"step\":1,\"unit\":\"min\"}},{\"abilityId\":110,\"accessMode\":\"ro\",\"code\":\"use_time_2\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-dp_time3\",\"attribute\":\"4096\",\"trigger\":\"direct\"},\"name\":\"使用时间2\",\"typeSpec\":{\"type\":\"value\",\"max\":86400,\"min\":0,\"scale\":0,\"step\":1,\"unit\":\"s\"}},{\"abilityId\":111,\"accessMode\":\"ro\",\"code\":\"use_time_1\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-dp_time3\",\"attribute\":\"4096\",\"trigger\":\"direct\"},\"name\":\"使用时间1\",\"typeSpec\":{\"type\":\"value\",\"max\":86400,\"min\":0,\"scale\":0,\"step\":1,\"unit\":\"s\"}},{\"abilityId\":112,\"accessMode\":\"ro\",\"code\":\"status_1\",\"description\":\"\",\"name\":\"状态1\",\"typeSpec\":{\"type\":\"enum\",\"range\":[\"manual\",\"auto\",\"idle\"]}},{\"abilityId\":113,\"accessMode\":\"ro\",\"code\":\"status_2\",\"description\":\"\",\"name\":\"状态2\",\"typeSpec\":{\"type\":\"enum\",\"range\":[\"manual\",\"auto\",\"idle\"]}},{\"abilityId\":114,\"accessMode\":\"rw\",\"code\":\"weather_delay2\",\"description\":\"\",\"name\":\"天气延时2\",\"typeSpec\":{\"type\":\"enum\",\"range\":[\"OFF\",\"1\",\"2\",\"3\",\"4\",\"5\",\"6\",\"7\"]}},{\"abilityId\":117,\"accessMode\":\"rw\",\"code\":\"weather_delay\",\"description\":\"\",\"extensions\":{\"iconName\":\"icon-dp_light2\",\"attribute\":\"4096\"},\"name\":\"天气延时\",\"typeSpec\":{\"type\":\"enum\",\"range\":[\"OFF\",\"1\",\"2\",\"3\",\"4\",\"5\",\"6\",\"7\"]}}]}]}"
  },
  "success": true,
  "t": 1782396637695,
  "tid": "a3d5caae709f11f180fff665632ead7a"
}
```

#### Gateway datapoint model

```json
{
  "result": {
    "model": "{\"modelId\":\"0000030kxe\",\"services\":[{\"actions\":[],\"code\":\"\",\"description\":\"\",\"events\":[],\"name\":\"默认服务\",\"properties\":[{\"abilityId\":1,\"accessMode\":\"ro\",\"code\":\"up_channel\",\"description\":\"数据传输上行通道\",\"extensions\":{\"iconName\":\"icon-dp_mode\",\"attribute\":\"640\"},\"name\":\"上行通道\",\"typeSpec\":{\"type\":\"raw\",\"maxlen\":128}},{\"abilityId\":2,\"accessMode\":\"wr\",\"code\":\"down_channel\",\"description\":\"数据传输下行通道\",\"extensions\":{\"iconName\":\"icon-dp_mode\",\"attribute\":\"640\"},\"name\":\"下行通道\",\"typeSpec\":{\"type\":\"raw\",\"maxlen\":128}}]}]}"
  },
  "success": true,
  "t": 1782396689113,
  "tid": "c280954d709f11f1a3fc1af992f77835"
}
```
