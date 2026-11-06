"""Config flow for Tuya BLE integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_DEVICE_ID
from homeassistant.core import callback
#from homeassistant.data_entry_flow import FlowResult

from .tuya_ble import SERVICE_UUID

from .const import (
    CONF_KEEP_CONNECTED,
    CONF_BLE_UNLOCK_CHECK,
    CONF_CATEGORY,
    CONF_DEVICE_NAME,
    CONF_LOCAL_KEY,
    CONF_PRODUCT_ID,
    CONF_PRODUCT_MODEL,
    CONF_PRODUCT_NAME,
    CONF_UUID,
    DOMAIN,
)
from .devices import get_device_readable_name, get_short_address
from .keyman import HASSTuyaBLEDeviceManager
from .schedule_flow import ScheduleOptionsFlow

_LOGGER = logging.getLogger(__name__)

SUPPORTED_SERVICE_UUIDS = {
    SERVICE_UUID,
    "0000fd50-0000-1000-8000-00805f9b34fb",
}

class TuyaBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._data: dict[str, Any] = {}
        self._manager: HASSTuyaBLEDeviceManager | None = None
        self._get_device_info_error = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return TuyaBLEOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup started from Add Integration."""
        return await self.async_step_device(user_input)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        if self._manager is None:
            self._manager = HASSTuyaBLEDeviceManager(self.hass, self._data)
        #await self._manager.build_cache()
        self.context["title_placeholders"] = {
            "name": await get_device_readable_name(
                discovery_info,
                self._manager,
            )
        }
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}
        if self._manager is None:
            self._manager = HASSTuyaBLEDeviceManager(self.hass, self._data)

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            local_name = await get_device_readable_name(discovery_info, self._manager)
            await self.async_set_unique_id(
                discovery_info.address, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            credentials = await self._manager.get_device_credentials(
                discovery_info.address, self._get_device_info_error, True
            )
            self._data[CONF_ADDRESS] = discovery_info.address
            if credentials is None:
                self._get_device_info_error = True
                return await self.async_step_credentials()
            else:
                return self.async_create_entry(
                    title=local_name,
                    data={CONF_ADDRESS: discovery_info.address},
                    options=self._data,
                )

        if discovery := self._discovery_info:
            self._discovered_devices[discovery.address] = discovery
        else:
            current_addresses = self._async_current_ids()
            for discovery in async_discovered_service_info(self.hass):
                if (
                    discovery.address in current_addresses
                    or discovery.address in self._discovered_devices
                    or discovery.service_data is None
                    or not SUPPORTED_SERVICE_UUIDS.intersection(discovery.service_data)
                ):
                    continue
                self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_unconfigured_devices")

        def_address: str
        if user_input:
            def_address = user_input.get(CONF_ADDRESS)
        else:
            def_address = list(self._discovered_devices)[0]

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=def_address,
                    ): vol.In(
                        {
                            service_info.address: await get_device_readable_name(
                                service_info,
                                self._manager,
                            )
                            for service_info in self._discovered_devices.values()
                        }
                    ),
                },
            ),
            errors=errors,
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual entry of device credentials not found in devices.json."""
        errors: dict[str, str] = {}

        if user_input is not None:
            credentials = self._manager.check_and_create_device_credentials(
                user_input.get(CONF_UUID),
                user_input.get(CONF_LOCAL_KEY),
                user_input.get(CONF_DEVICE_ID),
                user_input.get(CONF_CATEGORY),
                user_input.get(CONF_PRODUCT_ID),
                user_input.get(CONF_DEVICE_NAME),
                user_input.get(CONF_PRODUCT_NAME),
                user_input.get(CONF_PRODUCT_MODEL),
                user_input.get(CONF_BLE_UNLOCK_CHECK),
            )
            if credentials is None:
                errors["base"] = "invalid_credentials"
            else:
                self._data.update(user_input)
                title = (
                    user_input.get(CONF_DEVICE_NAME)
                    or user_input.get(CONF_PRODUCT_NAME)
                    or get_short_address(self._data[CONF_ADDRESS])
                )
                return self.async_create_entry(
                    title=title,
                    data={CONF_ADDRESS: self._data[CONF_ADDRESS]},
                    options=self._data,
                )

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UUID): str,
                    vol.Required(CONF_LOCAL_KEY): str,
                    vol.Required(CONF_DEVICE_ID): str,
                    vol.Required(CONF_CATEGORY): str,
                    vol.Required(CONF_PRODUCT_ID): str,
                    vol.Optional(CONF_DEVICE_NAME): str,
                    vol.Optional(CONF_PRODUCT_NAME): str,
                    vol.Optional(CONF_PRODUCT_MODEL): str,
                    vol.Optional(CONF_BLE_UNLOCK_CHECK): str,
                },
            ),
            errors=errors,
        )


class TuyaBLEOptionsFlow(ScheduleOptionsFlow):
    """Handle Tuya BLE options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        device = data.device if data else None
        if (
            user_input is None
            and getattr(device, "category", self.config_entry.options.get(CONF_CATEGORY))
            == "ggq"
            and getattr(device, "product_id", self.config_entry.options.get(CONF_PRODUCT_ID))
            == "qycalacn"
        ):
            return self.async_show_menu(
                step_id="init",
                menu_options=["manage_schedules", "connection_options"],
            )
        return await self.async_step_connection_options(user_input)

    async def async_step_connection_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage connection behavior without changing schedule state."""
        if user_input is not None:
            # Preserve existing credential/options keys written at setup time.
            options = dict(self.config_entry.options)
            options[CONF_KEEP_CONNECTED] = bool(
                user_input.get(CONF_KEEP_CONNECTED, False)
            )
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="connection_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_KEEP_CONNECTED,
                        default=bool(
                            self.config_entry.options.get(CONF_KEEP_CONNECTED, False)
                        ),
                    ): bool,
                }
            ),
        )
