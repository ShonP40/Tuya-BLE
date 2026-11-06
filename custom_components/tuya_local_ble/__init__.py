"""The Tuya BLE integration."""
from __future__ import annotations

import asyncio
import logging
import time

from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS, get_device

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .tuya_ble import TuyaBLEDevice

from .keyman import HASSTuyaBLEDeviceManager
from .const import DOMAIN
from .devices import TuyaBLECoordinator, TuyaBLEData, get_device_product_info

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.LOCK,
]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tuya BLE from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    # Seed the device with the last connectable advertisement Home Assistant
    # has seen, so RSSI / protocol version are known before the first connect.
    last_service_info = bluetooth.async_last_service_info(
        hass, address.upper(), True
    )
    ble_device = (
        last_service_info.device if last_service_info else None
    ) or bluetooth.async_ble_device_from_address(
        hass, address.upper(), True
    ) or await get_device(address)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Tuya BLE device with address {address}"
        )
    manager = HASSTuyaBLEDeviceManager(hass, entry.options.copy())
    device = TuyaBLEDevice(
        manager,
        ble_device,
        last_service_info.advertisement if last_service_info else None,
    )
    await device.initialize()

    def _last_seen() -> float | None:
        info = bluetooth.async_last_service_info(hass, address.upper(), True)
        return info.time if info else None

    device.set_last_seen_provider(_last_seen)
    product_info = get_device_product_info(device)

    coordinator = TuyaBLECoordinator(hass, device)

    last_raykube_advertisement_update = 0.0
    # Sleepy (advertisement-gated) devices: True once a status update has
    # succeeded, so later advertisements do not trigger needless reconnects.
    gated_status_received = False
    gated_update_task = None
    initial_update_task = None

    async def _async_update_raykube_from_advertisement() -> None:
        """Best-effort Raykube state refresh after a BLE advertisement."""
        try:
            await device.update()
        except BLEAK_EXCEPTIONS:
            _LOGGER.debug(
                "%s: Raykube advertisement-triggered update failed",
                address,
                exc_info=True,
            )
        except Exception:
            _LOGGER.debug(
                "%s: Raykube advertisement-triggered update failed unexpectedly",
                address,
                exc_info=True,
            )

    async def _async_gated_update() -> None:
        """Status refresh for advertisement-gated (sleepy) devices.

        Retries on a timer until it succeeds: Home Assistant does not call
        the advertisement callback for repeated identical advertisements,
        so waiting for the next callback can mean waiting forever.
        """
        nonlocal gated_status_received
        delay = 60
        while not gated_status_received:
            try:
                await device.update()
                gated_status_received = True
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug(
                    "%s: Status update failed; retrying in %ss",
                    address,
                    delay,
                    exc_info=True,
                )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 1800)

    @callback
    def _cancel_status_updates() -> None:
        for task in (gated_update_task, initial_update_task):
            if task is not None and not task.done():
                task.cancel()

    entry.async_on_unload(_cancel_status_updates)

    async def _async_initial_update() -> None:
        """Refresh ordinary devices without making startup wait for BLE."""
        delay = 60
        while True:
            try:
                async with asyncio.timeout(60):
                    await device.update()
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug(
                    "%s: Initial status refresh failed; retrying in %ss",
                    address,
                    delay,
                    exc_info=True,
                )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 1800)

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        nonlocal last_raykube_advertisement_update, gated_update_task
        device.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement
        )
        if device.is_advertisement_gated and not gated_status_received:
            # The device is awake right now; fetch its status while we can.
            if gated_update_task is None or gated_update_task.done():
                gated_update_task = entry.async_create_background_task(
                    hass, _async_gated_update(), f"{DOMAIN}_status_{address}"
                )
        if device.product_id in ("hc7n0urm", "y2yaegze"):
            # Raykube locks do not push manual/keypad state changes while the
            # integration is disconnected. A fresh advertisement after a
            # physical action is the safest low-power cue we have to reconnect
            # and request status, without keeping a permanent BLE session open.
            now = time.monotonic()
            if now - last_raykube_advertisement_update >= 300:
                last_raykube_advertisement_update = now
                hass.async_create_task(_async_update_raykube_from_advertisement())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    if device.is_advertisement_gated:
        # Do not block setup ("Initializing") waiting for a sleepy lock to
        # wake up. Entities are created now; status arrives on the next
        # advertisement (see _async_update_ble).
        # Background task: Home Assistant does not wait for these during
        # startup. A plain hass.async_create_task here held up HA startup for
        # minutes whenever the lock was out of reach.
        gated_update_task = entry.async_create_background_task(
            hass, _async_gated_update(), f"{DOMAIN}_status_{address}"
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = TuyaBLEData(
        entry.title,
        device,
        product_info,
        manager,
        coordinator,
        cancel_status_updates=_cancel_status_updates,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if not device.is_advertisement_gated:
        initial_update_task = entry.async_create_background_task(
            hass, _async_initial_update(), f"{DOMAIN}_status_{address}"
        )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        _cancel_status_updates()
        await device.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options (e.g. keep_connected) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: TuyaBLEData = hass.data[DOMAIN].pop(entry.entry_id)
        if data.cancel_status_updates is not None:
            data.cancel_status_updates()
        await data.device.stop()

    return unload_ok
