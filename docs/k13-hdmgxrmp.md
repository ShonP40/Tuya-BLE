# K13 (`hdmgxrmp`) experimental support

Product category: `jtmspro`  
Product ID: `hdmgxrmp`  
Marketing name observed: **K13** / Big Kids Room lock

## devices.json example

Create `/config/tuya_local_ble/devices.json`:

```json
{
  "DC:23:53:0C:4A:7A": {
    "address": "DC:23:53:0C:4A:7A",
    "uuid": "4f1b76766a8498d8",
    "local_key": "<local_key>",
    "device_id": "ebc3e5nip6bjkjre",
    "category": "jtmspro",
    "product_id": "hdmgxrmp",
    "device_name": "Big Kids Room Lock",
    "product_model": "K13",
    "product_name": "K13"
  }
}
```

Replace `<local_key>` with the key from TinyTuya / Tuya IoT.

## Mapped DPs (from Tuya cloud diagnostics)

| DP | Code | Role in this fork |
|----|------|-------------------|
| 8 | residual_electricity | Battery % sensor |
| 9 | battery_state | Battery enum sensor |
| 31 | beep_volume | Select (mute/normal) |
| 46 | manual_lock | Lock command |
| 47 | lock_motor_state | Lock state |
| 62 | unlock_phone_remote | Experimental unlock command |

## Expectations

- Requires BLE range (Pi adapter or Bluetooth proxy near the lock).
- Battery / status are the first goals.
- Remote unlock is experimental; `jtmspro` locks often need anti-replay / FD50 handling beyond a simple DP write.
