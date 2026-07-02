"""The Tuya BLE integration."""
from __future__ import annotations

from typing_extensions import Final

DOMAIN: Final = "tuya_local_ble"

DEVICE_METADATA_UUIDS: Final = "uuids"

DEVICE_DEF_MANUFACTURER: Final = "Tuya"
SET_DISCONNECTED_DELAY = 10 * 60

CONF_UUID: Final = "uuid"
CONF_LOCAL_KEY: Final = "local_key"
CONF_CATEGORY: Final = "category"
CONF_PRODUCT_ID: Final = "product_id"
CONF_DEVICE_NAME: Final = "device_name"
CONF_PRODUCT_MODEL: Final = "product_model"
CONF_PRODUCT_NAME: Final = "product_name"
CONF_BLE_UNLOCK_CHECK: Final = "ble_unlock_check"

CONF_CRED_FILE = DOMAIN + "/devices.json"

BATTERY_STATE_LOW: Final = "low"
BATTERY_STATE_NORMAL: Final = "normal"
BATTERY_STATE_HIGH: Final = "high"

BATTERY_NOT_CHARGING: Final = "not_charging"
BATTERY_CHARGING: Final = "charging"
BATTERY_CHARGED: Final = "charged"

CO2_LEVEL_NORMAL: Final = "normal"
CO2_LEVEL_ALARM: Final = "alarm"

FINGERBOT_MODE_PUSH: Final = "push"
FINGERBOT_MODE_SWITCH: Final = "switch"
FINGERBOT_MODE_PROGRAM: Final = "program"
FINGERBOT_BUTTON_EVENT: Final = "fingerbot_button_pressed"
