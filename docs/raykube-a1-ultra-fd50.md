# Raykube A1 Ultra / A1 Pro Max TuyaOS FD50 lock

This branch adds experimental local BLE support for Raykube A1 Ultra / A1 Pro Max locks using TuyaOS FD50 BLE service.

## Tested device

- Category: `jtmspro`
- Product ID: `hc7n0urm`
- BLE service UUID: `0000fd50-0000-1000-8000-00805f9b34fb`
- GATT write characteristic: `00000001-0000-1001-8001-00805f9b07d0`
- GATT notify characteristic: `00000002-0000-1001-8001-00805f9b07d0`

## What works

- Discovery through the FD50 service UUID.
- Connection on BlueZ/Bleak without `AcquireNotify` conflicts by forcing StartNotify.
- Tuya BLE `DEVICE_INFO` handshake variant used by this lock.
- Local remote unlock through Tuya BLE V4 command framing.
- Basic V4 datapoint/event parsing for future state handling.

## Current limitation

Remote unlock and remote lock have both been physically verified. Remote unlock uses a device-specific `ble_unlock_check` V4 payload. Remote lock uses the `manual_lock` datapoint (`46`) in V4 framing.

## Required `devices.json` fields

Use the same shape as other devices, with the Raykube product ID:

```json
{
  "XX:XX:XX:XX:XX:XX": {
    "address": "XX:XX:XX:XX:XX:XX",
    "uuid": "<device UUID>",
    "local_key": "<device local key>",
    "device_id": "<device ID>",
    "category": "jtmspro",
    "product_id": "hc7n0urm",
    "device_name": "Raykube A1 Ultra",
    "product_model": "A1 Ultra",
    "product_name": "Smart lock",
    "ble_unlock_check": "<base64 raw Tuya status value>"
  }
}
```

Do not publish your real `uuid`, `local_key`, `device_id`, or `ble_unlock_check`.

`ble_unlock_check` is the raw base64 status value reported by Tuya Cloud for the device. It is device-specific and is used to build the V4 remote-unlock command. You can obtain it from the Tuya IoT OpenAPI device details/status response where the status code is `ble_unlock_check`.

## Protocol notes

The official app trace showed that this lock differs from older Gimdow-style Tuya BLE locks:

- `DEVICE_INFO` is sent with payload `00 f3`.
- The first packet uses protocol marker `0x20`.
- The lock expects the encrypted `DEVICE_INFO` frame as one larger ATT write after MTU exchange; splitting it into 20-byte chunks timed out.
- Legacy `FUN_SENDER_DPS` boolean writes can be acknowledged at the BLE/session layer but do not actuate the motor.
- Remote unlock uses `FUN_SENDER_DPS_V4` (`0x0027`) framing.

The V4 state/event schema is not fully reverse-engineered yet. Remote unlock is generated from the device-specific `ble_unlock_check` value; remote lock uses `manual_lock` DP46 in V4 framing.
