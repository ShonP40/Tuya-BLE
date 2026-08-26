"""Light platform for Tuya BLE CCT lights."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .const import DOMAIN
from .devices import TuyaBLEData, TuyaBLEEntity, TuyaBLEProductInfo
from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice

_LOGGER = logging.getLogger(__name__)


@dataclass
class TuyaBLELightMapping:
    """Per-product mapping for a Tuya BLE CCT light.

    DP family: modern = switch_led 20 / work_mode 21 / bright_value 22 /
    temp_value 23. Legacy family (DP 1/2/3) is a future follow-up.
    """

    switch_dp: int
    bright_dp: int
    temp_dp: int
    description: LightEntityDescription
    work_mode_dp: int | None = None
    bright_scale: tuple[int, int] = (10, 1000)  # raw range, modern family
    min_color_temp_kelvin: int = 2700
    max_color_temp_kelvin: int = 6500


@dataclass
class TuyaBLECategoryLightMapping:
    """Category + per-product CCT light mapping table."""

    products: dict[str, list[TuyaBLELightMapping]] | None = None
    mapping: list[TuyaBLELightMapping] | None = None


# Shared mapping list for all common CCT light categories. The DP family
# (modern: switch_led 20 / work_mode 21 / bright_value 22 / temp_value 23)
# is identical across these categories — only the category key differs.
_CCT_MAPPING_LIST: list[TuyaBLELightMapping] = [
    TuyaBLELightMapping(
        switch_dp=20,  # switch_led (mandatory for entity to load)
        work_mode_dp=21,  # work_mode (optional, written if present)
        bright_dp=22,  # bright_value (raw 10..1000)
        temp_dp=23,  # temp_value (raw 0..1000; 0=cool 6500K, 1000=warm 2700K)
        description=LightEntityDescription(
            key="light",
            translation_key="light",
        ),
    ),
]

# Register under the common Tuya light category strings. The setup-time
# log line surfaces the actual category so the user can add more keys if
# their device uses an unlisted one.
mapping: dict[str, TuyaBLECategoryLightMapping] = {
    cat: TuyaBLECategoryLightMapping(
        products={},  # populated by user via devices.json (per-product overrides)
        mapping=_CCT_MAPPING_LIST,
    )
    for cat in ("dj", "dmd", "fwd", "yyd", "xdd")
}


def get_mapping_by_device(device: TuyaBLEDevice) -> list[TuyaBLELightMapping]:
    """Return the mapping list for a device, falling back to category default."""
    category = mapping.get(device.category)
    if category is not None and category.products is not None:
        product_mapping = category.products.get(device.product_id)
        if product_mapping is not None:
            return product_mapping
        if category.mapping is not None:
            return category.mapping
    return []


def _kelvin_to_raw(kelvin: int, lo: int, hi: int) -> int:
    """Convert kelvin to raw DP value (raw 0=warmest, raw 1000=coolest)."""
    kelvin = max(lo, min(hi, kelvin))
    span = hi - lo
    raw = round((hi - kelvin) * 1000 / span)
    return max(0, min(1000, raw))


def _raw_to_kelvin(raw: int, lo: int, hi: int) -> int:
    """Convert raw DP value back to kelvin."""
    raw = max(0, min(1000, raw))
    span = hi - lo
    kelvin = round(hi - raw * span / 1000)
    return max(lo, min(hi, kelvin))


class TuyaBLELight(TuyaBLEEntity, LightEntity):
    """Representation of a Tuya BLE CCT light."""

    _attr_supported_color_modes: set[ColorMode] = {ColorMode.COLOR_TEMP}
    _attr_color_mode: ColorMode = ColorMode.COLOR_TEMP
    # Neutral default; replaced by device push on first notify.
    _attr_color_temp_kelvin: int | None = 4000

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: TuyaBLEDevice,
        product: TuyaBLEProductInfo,
        light_mapping: TuyaBLELightMapping,
    ) -> None:
        super().__init__(
            hass, coordinator, device, product, light_mapping.description
        )
        self._light_mapping = light_mapping
        self._attr_min_color_temp_kelvin = light_mapping.min_color_temp_kelvin
        self._attr_max_color_temp_kelvin = light_mapping.max_color_temp_kelvin

    @callback
    def _handle_coordinator_update(self) -> None:
        """Re-read DPs on BLE push and refresh HA state."""
        datapoints = self._device.datapoints

        switch_dp = datapoints[self._light_mapping.switch_dp]
        if switch_dp is not None:
            self._attr_is_on = bool(switch_dp.value)

        bright_dp = datapoints[self._light_mapping.bright_dp]
        if bright_dp is not None:
            lo, hi = self._light_mapping.bright_scale
            self._attr_brightness = value_to_brightness(
                (lo, hi), int(bright_dp.value)
            )

        temp_dp = datapoints[self._light_mapping.temp_dp]
        if temp_dp is not None:
            lo, hi = (
                self._light_mapping.min_color_temp_kelvin,
                self._light_mapping.max_color_temp_kelvin,
            )
            self._attr_color_temp_kelvin = _raw_to_kelvin(int(temp_dp.value), lo, hi)

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally with brightness and color temperature.

        All DP writes are batched in `begin_update()`/`end_update()` so the
        vendored library emits a single BLE packet via `_send_datapoints_v3`.
        """
        device = self._device
        datapoints = device.datapoints

        # Optimistic state — REQ-LIGHT-011
        self._attr_is_on = True
        if ATTR_BRIGHTNESS in kwargs and kwargs[ATTR_BRIGHTNESS] is not None:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
        if (
            ATTR_COLOR_TEMP_KELVIN in kwargs
            and kwargs[ATTR_COLOR_TEMP_KELVIN] is not None
        ):
            self._attr_color_temp_kelvin = max(
                self._attr_min_color_temp_kelvin,
                min(self._attr_max_color_temp_kelvin, kwargs[ATTR_COLOR_TEMP_KELVIN]),
            )
        self.async_write_ha_state()

        # Batched single-packet write — REQ-LIGHT-007
        datapoints.begin_update()
        try:
            # DP 20 switch_led=True (mandatory for the family gate)
            switch = datapoints.get_or_create(
                self._light_mapping.switch_dp,
                TuyaBLEDataPointType.DT_BOOL,
                True,
            )
            await switch.set_value(True)

            # DP 21 work_mode="white" — only if the device actually has it
            if (
                self._light_mapping.work_mode_dp is not None
                and datapoints.has_id(self._light_mapping.work_mode_dp)
            ):
                mode = datapoints.get_or_create(
                    self._light_mapping.work_mode_dp,
                    TuyaBLEDataPointType.DT_STRING,
                    "white",
                )
                await mode.set_value("white")

            # DP 22 bright_value — only if HA passed brightness
            if ATTR_BRIGHTNESS in kwargs and kwargs[ATTR_BRIGHTNESS] is not None:
                lo, hi = self._light_mapping.bright_scale
                raw = brightness_to_value((lo, hi), kwargs[ATTR_BRIGHTNESS])
                bright = datapoints.get_or_create(
                    self._light_mapping.bright_dp,
                    TuyaBLEDataPointType.DT_VALUE,
                    raw,
                )
                await bright.set_value(raw)

            # DP 23 temp_value — only if HA passed color_temp_kelvin
            if (
                ATTR_COLOR_TEMP_KELVIN in kwargs
                and kwargs[ATTR_COLOR_TEMP_KELVIN] is not None
            ):
                lo, hi = (
                    self._light_mapping.min_color_temp_kelvin,
                    self._light_mapping.max_color_temp_kelvin,
                )
                raw = _kelvin_to_raw(kwargs[ATTR_COLOR_TEMP_KELVIN], lo, hi)
                temp = datapoints.get_or_create(
                    self._light_mapping.temp_dp,
                    TuyaBLEDataPointType.DT_VALUE,
                    raw,
                )
                await temp.set_value(raw)

            await datapoints.end_update()  # ONE BLE packet via _send_datapoints_v3
        except Exception:
            # Vendored tuya_ble exposes no public abort API; defensively clean
            # the batch buffer so the next BLE push re-syncs cleanly.
            if datapoints._update_started > 0:
                _LOGGER.warning(
                    "TuyaBLE light %s: batched update aborted before end_update; "
                    "buffer cleared, awaiting next device push",
                    device.address,
                )
                datapoints._updated_datapoints = []
                datapoints._update_started = 0
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off (writes DP 20 only)."""
        self._attr_is_on = False
        self.async_write_ha_state()

        device = self._device
        datapoints = device.datapoints
        datapoints.begin_update()
        try:
            switch = datapoints.get_or_create(
                self._light_mapping.switch_dp,
                TuyaBLEDataPointType.DT_BOOL,
                False,
            )
            await switch.set_value(False)
            await datapoints.end_update()
        except Exception:
            if datapoints._update_started > 0:
                _LOGGER.warning(
                    "TuyaBLE light %s: batched update aborted before end_update; "
                    "buffer cleared, awaiting next device push",
                    device.address,
                )
                datapoints._updated_datapoints = []
                datapoints._update_started = 0
            raise


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tuya BLE CCT lights from a config entry."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    device = data.device

    # DP-family gate: only create the entity if the modern-family switch DP
    # (20) is reported as a bool. If absent, the bulb is legacy-family or
    # hasn't advertised yet — log and skip rather than load a broken entity.
    if not device.datapoints.has_id(20, TuyaBLEDataPointType.DT_BOOL):
        _LOGGER.warning(
            "TuyaBLE light: device %s missing DP 20 (modern switch_led); skipping",
            device.address,
        )
        return

    # Surface the device category so the user can confirm one of the
    # registered category keys (dj/dmd/fwd/yyd/xdd) matches their
    # devices.json entry (REQ-LIGHT-002 fallback).
    _LOGGER.info(
        "TuyaBLE light setup: device_id=%s category=%s product_id=%s",
        device.device_id,
        device.category,
        device.product_id,
    )

    mappings = get_mapping_by_device(device)
    if not mappings:
        return
    async_add_entities(
        TuyaBLELight(hass, data.coordinator, device, data.product, light_mapping)
        for light_mapping in mappings
    )