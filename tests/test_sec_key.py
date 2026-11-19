"""Key derivation for Tuya "new-security" BLE devices (sec_key)."""

import hashlib
import unittest
from unittest.mock import AsyncMock, MagicMock

from custom_components.tuya_local_ble.tuya_ble.manager import (
    AbstaractTuyaBLEDeviceManager,
)
from custom_components.tuya_local_ble.tuya_ble.tuya_ble import TuyaBLEDevice

LOCAL_KEY = "abcdefghijklmnop"
SEC_KEY = "0123456789ABCDEF"


def _device(sec_key):
    creds = AbstaractTuyaBLEDeviceManager.check_and_create_device_credentials(
        "uuid0000", LOCAL_KEY, "device0", "jtmspro", "qymgyczo",
        None, None, None, None, sec_key,
    )
    manager = MagicMock()
    manager.get_device_credentials = AsyncMock(return_value=creds)
    ble_device = MagicMock()
    ble_device.address = "00:11:22:33:44:55"
    return TuyaBLEDevice(manager, ble_device)


class SecKeyTests(unittest.IsolatedAsyncioTestCase):
    async def test_classic_keys_without_sec_key(self):
        device = _device(None)
        self.assertTrue(await device._update_device_info())
        self.assertEqual(device._login_flag, 4)
        self.assertEqual(device._session_flag, 5)
        self.assertEqual(
            device._login_key, hashlib.md5(LOCAL_KEY[:6].encode()).digest()
        )

    async def test_new_security_keys_with_sec_key(self):
        device = _device(SEC_KEY)
        self.assertTrue(await device._update_device_info())
        self.assertEqual(device._login_flag, 14)
        self.assertEqual(device._session_flag, 15)
        material = (LOCAL_KEY + SEC_KEY).encode()
        self.assertEqual(device._login_key, hashlib.md5(material).digest())
        self.assertEqual(device._get_key(14), device._login_key)
        # Pairing still carries the 6-byte local key.
        self.assertEqual(device._local_key, LOCAL_KEY[:6].encode())

    def test_empty_sec_key_is_treated_as_absent(self):
        creds = AbstaractTuyaBLEDeviceManager.check_and_create_device_credentials(
            "uuid0000", LOCAL_KEY, "device0", "jtmspro", "qymgyczo",
            None, None, None, None, "",
        )
        self.assertIsNone(creds.sec_key)


if __name__ == "__main__":
    unittest.main()
