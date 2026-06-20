"""The Tuya BLE integration."""
from __future__ import annotations

import logging
import json
import os
import aiofiles

from typing import Any

from homeassistant.const import CONF_ADDRESS, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant

from .tuya_ble import (
    AbstaractTuyaBLEDeviceManager,
    TuyaBLEDeviceCredentials,
)

from .const import (
    CONF_CRED_FILE,
    CONF_PRODUCT_MODEL,
    CONF_UUID,
    CONF_LOCAL_KEY,
    CONF_CATEGORY,
    CONF_PRODUCT_ID,
    CONF_DEVICE_NAME,
    CONF_PRODUCT_NAME,
    CONF_BLE_UNLOCK_CHECK,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_TUYA_DEVICE_KEYS = [
    CONF_UUID,
    CONF_LOCAL_KEY,
    CONF_DEVICE_ID,
    CONF_CATEGORY,
    CONF_PRODUCT_ID,
    CONF_DEVICE_NAME,
    CONF_PRODUCT_NAME,
    CONF_PRODUCT_MODEL,
    CONF_BLE_UNLOCK_CHECK,
]

class HASSTuyaBLEDeviceManager(AbstaractTuyaBLEDeviceManager):
    """Cloud connected manager of the Tuya BLE devices credentials."""

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        assert hass is not None
        self._hass = hass
        self._data = data
        self._devicedata = None
        
        #devicedata_path = os.path.join(self._hass.config.config_dir, CONF_CRED_FILE)
        #f = open(devicedata_path)
        #self._devicedata = json.load(f)

    async def load_device_config(self):
        devicedata_path = os.path.join(self._hass.config.config_dir, CONF_CRED_FILE)

        async with aiofiles.open(devicedata_path, mode='r') as f:
            contents = await f.read()
        self._devicedata = json.loads(contents)


    async def get_device_credentials(
        self,
        address: str,
        force_update: bool = False,
        save_data: bool = False,
    ) -> TuyaBLEDeviceCredentials | None:
        """Get credentials of the Tuya BLE device."""
        credentials: dict[str, any] | None = None
        result: TuyaBLEDeviceCredentials | None = None
        
        if self._devicedata == None:
            await self.load_device_config()

        credentials = self._devicedata.get(address)

        if credentials:
            result = TuyaBLEDeviceCredentials(
                credentials.get(CONF_UUID, ""),
                credentials.get(CONF_LOCAL_KEY, ""),
                credentials.get(CONF_DEVICE_ID, ""),
                credentials.get(CONF_CATEGORY, ""),
                credentials.get(CONF_PRODUCT_ID, ""),
                credentials.get(CONF_DEVICE_NAME, ""),
                credentials.get(CONF_PRODUCT_MODEL, ""),
                credentials.get(CONF_PRODUCT_NAME, ""),
                credentials.get(CONF_BLE_UNLOCK_CHECK, ""),
            )
            _LOGGER.debug("Retrieved: %s", result)

        return result

    @property
    def data(self) -> dict[str, Any]:
        return self._data
