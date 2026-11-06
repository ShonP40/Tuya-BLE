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

        try:
            async with aiofiles.open(devicedata_path, mode='r') as f:
                contents = await f.read()
            self._devicedata = json.loads(contents)
        except FileNotFoundError:
            self._devicedata = {}


    async def get_device_credentials(
        self,
        address: str,
        force_update: bool = False,
        save_data: bool = False,
    ) -> TuyaBLEDeviceCredentials | None:
        """Get credentials of the Tuya BLE device."""
        result = self._credentials_from_options(address)
        if result:
            return result

        credentials: dict[str, any] | None = None
        result = None

        if self._devicedata == None:
            await self.load_device_config()

        _LOGGER.warning("Lookup address = '%s'", address)
        _LOGGER.warning("Available keys = %s", list(self._devicedata.keys()))

        credentials = self._devicedata.get(address)

        _LOGGER.warning("Credentials = %r", list(self._devicedata.get(address) or []))

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

    def _credentials_from_options(
        self, address: str
    ) -> TuyaBLEDeviceCredentials | None:
        """Build credentials from the config entry's options, if present."""
        if self._data.get(CONF_ADDRESS) != address:
            return None
        return self.check_and_create_device_credentials(
            *(self._data.get(key) for key in CONF_TUYA_DEVICE_KEYS)
        )

    @property
    def data(self) -> dict[str, Any]:
        return self._data
