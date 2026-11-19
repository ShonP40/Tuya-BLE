# Evanshow Bluetooth lever handles (`n1qxwwic`, `qymgyczo`)

Two Evanshow Bluetooth lever handle locks, category `jtmspro`. Both use the
standard jtmspro lock datapoints: DP6 unlock trigger, DP46 `manual_lock`,
DP47 `lock_motor_state` (`False` = locked), DP71 `ble_unlock_check`. Both
handles relock on their own about a second after an unlock, so Home
Assistant shows the lock as locked again right after it unlocks.

## `n1qxwwic`: legacy A201 GATT

It uses the generic protocol-3 path with no extra setup beyond the usual
credentials. Unlock and live state were verified on real hardware through an
ESPHome Bluetooth proxy.

## `qymgyczo`: FD50 GATT, Tuya "new-security"

- It advertises only the FD50 service, with no manufacturer data.
- With the classic login (flag `0x04`, `MD5(local_key[:6])`) the lock drops
  the link about 100 ms after `FUN_SENDER_DEVICE_INFO`. This is the same
  symptom reported for other FD50 locks in #22, #43, #48 and #51.
- Login works once the keys are derived Tuya's "new-security" way:

| Step | Flag | AES key |
|---|---|---|
| `FUN_SENDER_DEVICE_INFO` | `0x0E` | `MD5(local_key + sec_key)` |
| Everything after it | `0x0F` | `MD5(local_key + sec_key + srand)` |

`srand` is bytes 6..12 of the DEVICE_INFO response, as before. The pairing
request still carries `local_key[:6]`. Everything after login is the existing
TuyaOS FD50 path used for `nglqaett`/`y2yaegze`:

- strict V4 report decoding: DP47 reports `True` on unlock and `False` on relock
- the DP71 V4 remote unlock built from `ble_unlock_check`

Verified on real hardware: connect, status snapshot, and remote unlock.

### Credentials

`devices.json` needs both `sec_key` and `ble_unlock_check`:

```json
{
  "XX:XX:XX:XX:XX:XX": {
    "address": "XX:XX:XX:XX:XX:XX",
    "uuid": "<uuid>",
    "local_key": "<local key>",
    "device_id": "<device id>",
    "category": "jtmspro",
    "product_id": "qymgyczo",
    "ble_unlock_check": "<base64 DP71 value from the cloud>",
    "sec_key": "<16-character secKey>"
  }
}
```

Where the two values come from:

- **`sec_key`:** the Tuya OpenAPI (TinyTuya) does not return it. The Tuya /
  Smart Life mobile app API does (`secKey` on the device record).
- **`ble_unlock_check`:** the cloud value can be empty until the lock has been
  unlocked once from the Tuya app.

### Phone app coexistence

The lock accepts a single BLE connection and does not hang up an idle link
itself. While Home Assistant held the link, the Tuya app could not reach the
lock. So `qymgyczo` is now:

- **advertisement-gated:** it connects on demand only;
- **released after use:** it disconnects 15 s after a status read or a command
  (`RELEASE_IDLE_LINK_PRODUCTS`).
