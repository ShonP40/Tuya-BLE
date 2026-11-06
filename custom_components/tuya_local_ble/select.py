"""The Tuya BLE integration."""
from __future__ import annotations

from dataclasses import dataclass, field

import logging

from homeassistant.components.select import (
    SelectEntityDescription,
    SelectEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    FINGERBOT_MODE_PROGRAM,
    FINGERBOT_MODE_PUSH,
    FINGERBOT_MODE_SWITCH,
)
from .devices import TuyaBLEData, TuyaBLEEntity, TuyaBLEProductInfo
from .tuya_ble import TuyaBLEDataPointType, TuyaBLEDevice

_LOGGER = logging.getLogger(__name__)


@dataclass
class TuyaBLESelectMapping:
    dp_id: int
    description: SelectEntityDescription
    force_add: bool = True
    dp_type: TuyaBLEDataPointType | None = None


@dataclass
class TemperatureUnitDescription(SelectEntityDescription):
    key: str = "temperature_unit"
    icon: str = "mdi:thermometer"
    entity_category: EntityCategory = EntityCategory.CONFIG


@dataclass
class TuyaBLEFingerbotModeMapping(TuyaBLESelectMapping):
    description: SelectEntityDescription = field(
        default_factory=lambda: SelectEntityDescription(
            key="fingerbot_mode",
            entity_category=EntityCategory.CONFIG,
            options=
                [
                    FINGERBOT_MODE_PUSH, 
                    FINGERBOT_MODE_SWITCH,
                    FINGERBOT_MODE_PROGRAM,
                ],
        )
    )


@dataclass
class TuyaBLECategorySelectMapping:
    products: dict[str, list[TuyaBLESelectMapping]] | None = None
    mapping: list[TuyaBLESelectMapping] | None = None


mapping: dict[str, TuyaBLECategorySelectMapping] = {
    "co2bj": TuyaBLECategorySelectMapping(
        products={
            "59s19z5m":  # CO2 Detector
            [
                TuyaBLESelectMapping(
                    dp_id=101,
                    description=TemperatureUnitDescription(
                        options=[
                            UnitOfTemperature.CELSIUS,
                            UnitOfTemperature.FAHRENHEIT,
                        ],
                    )
                ),
            ],
        },
    ),
    "ms": TuyaBLECategorySelectMapping(
        products={
            **dict.fromkeys(
                ["ludzroix", "isk2p555"], # Smart Lock
                [
                    TuyaBLESelectMapping(
                        dp_id=31,
                        description=SelectEntityDescription(
                            key="beep_volume",
                            options=[
                                "mute",
                                "low",
                                "normal",
                                "high",
                            ],
                            entity_category=EntityCategory.CONFIG,
                        ),
                    ),
                ]
            ),
        }
    ),
    "jtmspro": TuyaBLECategorySelectMapping(
        products={
            "rlyxv7pe":  # Smart Lock
            [
                TuyaBLESelectMapping(
                    dp_id=31,
                    description=SelectEntityDescription(
                        key="beep_volume",
                        options=[
                            "mute",
                            "low",
                            "normal",
                            "high",
                        ],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
                TuyaBLESelectMapping(
                    dp_id=48,
                    description=SelectEntityDescription(
                        key="lock_direction",
                        options=[
                            "clockwise",
                            "anticlockwise",
                        ],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
            ],
            "hc7n0urm":  # Raykube A1 Ultra / A1 Pro Max TuyaOS FD50 lock
            [
                TuyaBLESelectMapping(
                    dp_id=31,
                    description=SelectEntityDescription(
                        key="beep_volume",
                        options=[
                            "mute",
                            "low",
                            "normal",
                            "high",
                        ],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
                TuyaBLESelectMapping(
                    dp_id=48,
                    description=SelectEntityDescription(
                        key="lock_direction",
                        options=[
                            "clockwise",
                            "anticlockwise",
                        ],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
            ],
            "ikphogdj":  # HL Knob-2, TuyaOS FD50 transport
            [
                # dp 31 (beep_volume) confirmed present in cloud DP schema.
                # dp 48 (lock_direction) confirmed NOT a valid datapoint for
                # this product - not present in cloud properties, removed.
                TuyaBLESelectMapping(
                    dp_id=31,
                    description=SelectEntityDescription(
                        key="beep_volume",
                        options=[
                            "mute",
                            "low",
                            "normal",
                            "high",
                        ],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
            ],
            "nglqaett":  # HTMCKM5 B5
            [
                TuyaBLESelectMapping(
                    dp_id=31,
                    description=SelectEntityDescription(
                        key="beep_volume",
                        options=[
                            "mute",
                            "high",
                        ],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
            ],
        }
    ),    
    "szjqr": TuyaBLECategorySelectMapping(
        products={
            **dict.fromkeys(
                ["3yqdo5yt", "xhf790if"],  # CubeTouch 1s and II
                [
                    TuyaBLEFingerbotModeMapping(dp_id=2),
                ],
            ),
            **dict.fromkeys(
                [
                    "blliqpsj",
                    "ndvkgsrm",
                    "yiihr7zh", 
                    "neq16kgd"
                ],  # Fingerbot Plus
                [
                    TuyaBLEFingerbotModeMapping(dp_id=8),
                ],
            ),
            **dict.fromkeys(
                ["ltak7e1p", "y6kttvd6", "yrnk7mnn",
                    "nvr2rocq", "bnt7wajf", "rvdceqjh",
                    "5xhbk964"],  # Fingerbot
                [
                    TuyaBLEFingerbotModeMapping(dp_id=8),
                ],
            ),
        },
    ),
    "wsdcg": TuyaBLECategorySelectMapping(
        products={
            "ojzlzzsw":  # Soil moisture sensor
            [
                TuyaBLESelectMapping(
                    dp_id=9,
                    description=TemperatureUnitDescription(
                        options=[
                            UnitOfTemperature.CELSIUS,
                            UnitOfTemperature.FAHRENHEIT,
                        ],
                        entity_registry_enabled_default=False,
                    )
                ),
            ],
            "jm6iasmb":  # Temperature Humidity Sensor
            [
                TuyaBLESelectMapping(
                    dp_id=9,
                    description=TemperatureUnitDescription(
                        options=[
                            UnitOfTemperature.CELSIUS,
                            UnitOfTemperature.FAHRENHEIT,
                        ],
                        entity_registry_enabled_default=False,
                    )
                ),
            ],
        },
    ),
    "znhsb": TuyaBLECategorySelectMapping(
        products={
            "cdlandip":  # Smart water bottle
            [
                TuyaBLESelectMapping(
                    dp_id=106,
                    description=TemperatureUnitDescription(
                        options=[
                            UnitOfTemperature.CELSIUS,
                            UnitOfTemperature.FAHRENHEIT,
                        ],
                    )
                ),
                TuyaBLESelectMapping(
                    dp_id=107,
                    description=SelectEntityDescription(
                        key="reminder_mode",
                        options=[
                            "interval_reminder",
                            "schedule_reminder",
                        ],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
            ],
        },
    ),
    "znhsb": TuyaBLECategorySelectMapping(
        products={
            "cdlandip":  # Smart water bottle
            [
                TuyaBLESelectMapping(
                    dp_id=106,
                    description=TemperatureUnitDescription(
                        options=[
                            UnitOfTemperature.CELSIUS,
                            UnitOfTemperature.FAHRENHEIT,
                        ],
                    )
                ),
                TuyaBLESelectMapping(
                    dp_id=107,
                    description=SelectEntityDescription(
                        key="reminder_mode",
                        options=[
                            "interval_reminder",
                            "alarm_reminder",
                        ],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
            ],
        },
    ),
    "ggq": TuyaBLECategorySelectMapping(
        products={
            "qycalacn": [  # Hoselink Dual-Outlet Tap Timer
                TuyaBLESelectMapping(
                    dp_id=117,
                    description=SelectEntityDescription(
                        key="weather_delay",
                        icon="mdi:weather-rainy",
                        options=["off", "1", "2", "3", "4", "5", "6", "7"],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
                TuyaBLESelectMapping(
                    dp_id=114,
                    description=SelectEntityDescription(
                        key="weather_delay2",
                        icon="mdi:weather-rainy",
                        options=["off", "1", "2", "3", "4", "5", "6", "7"],
                        entity_category=EntityCategory.CONFIG,
                    ),
                ),
            ],
        },
    ),
}


def get_mapping_by_device(
    device: TuyaBLEDevice
) -> list[TuyaBLECategorySelectMapping]:
    category = mapping.get(device.category)
    if category is not None and category.products is not None:
        product_mapping = category.products.get(device.product_id)
        if product_mapping is not None:
            return product_mapping
        if category.mapping is not None:
            return category.mapping
        else:
            return []
    else:
        return []


class TuyaBLESelect(TuyaBLEEntity, SelectEntity):
    """Representation of a Tuya BLE select."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: TuyaBLEDevice,
        product: TuyaBLEProductInfo,
        mapping: TuyaBLESelectMapping,
    ) -> None:
        super().__init__(
            hass,
            coordinator,
            device,
            product,
            mapping.description
        )
        self._mapping = mapping
        self._attr_options = mapping.description.options
        # Raykube volume/direction often lack a durable DP echo. Keep last known
        # option so coordinator updates from lock reverse-sync do not wipe HA state.
        self._sticky_option: str | None = None

    def _is_raykube_sticky_select(self) -> bool:
        if self._device.product_id == "hc7n0urm":
            return self._mapping.dp_id in (31, 48)
        if self._device.product_id == "ikphogdj":
            return self._mapping.dp_id in (31, 48)
        return False

    def _option_from_datapoint(self) -> str | None:
        datapoint = self._device.datapoints[self._mapping.dp_id]
        if not datapoint:
            return None
        value = datapoint.value
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            return value if isinstance(value, str) and value in self._attr_options else None
        if 0 <= int_value < len(self._attr_options):
            return self._attr_options[int_value]
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._is_raykube_sticky_select():
            return True
        return super().available

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        option = self._option_from_datapoint()
        if option is not None:
            self._sticky_option = option
            return option
        if self._is_raykube_sticky_select() and self._sticky_option in self._attr_options:
            return self._sticky_option
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option and push local state immediately."""
        if option not in self._attr_options:
            return
        int_value = self._attr_options.index(option)
        datapoint = self._device.datapoints.get_or_create(
            self._mapping.dp_id,
            TuyaBLEDataPointType.DT_ENUM,
            int_value,
        )
        if not datapoint:
            return
        await datapoint.set_value(int_value)
        # Optimistic + sticky HA state: Raykube often ACKs V4 writes without
        # echoing DP31/DP48, and later lock events can refresh entities without
        # those DPs present.
        self._sticky_option = option
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tuya BLE sensors."""
    data: TuyaBLEData = hass.data[DOMAIN][entry.entry_id]
    if data.device.category == "ggq" and data.device.product_id == "qycalacn":
        registry = er.async_get(hass)
        for key in ("weather_delay", "weather_delay2"):
            entity_id = registry.async_get_entity_id(
                "select", DOMAIN, f"{data.device.device_id}-{key}"
            )
            if (
                entity_id
                and registry.async_get(entity_id).disabled_by
                == er.RegistryEntryDisabler.INTEGRATION
            ):
                registry.async_update_entity(entity_id, disabled_by=None)
    mappings = get_mapping_by_device(data.device)
    entities: list[TuyaBLESelect] = []
    for mapping in mappings:
        if (
            mapping.force_add or
            data.device.datapoints.has_id(mapping.dp_id, mapping.dp_type)
        ):
            entities.append(TuyaBLESelect(
                hass,
                data.coordinator,
                data.device,
                data.product,
                mapping,
            ))
    async_add_entities(entities)
