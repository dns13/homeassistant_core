"""Support for VeSync numeric entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import override

from pyvesync.base_devices import VeSyncFanBase
from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.device_container import DeviceContainer
from pyvesync.utils.helpers import OscillationRange

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import DEGREE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_fan, is_humidifier
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def _mist_levels(device: VeSyncBaseDevice) -> list[int]:
    """Check if the device supports mist level adjustment."""
    if is_humidifier(device):
        return device.mist_levels
    raise HomeAssistantError("Device does not support mist level adjustment.")


def _set_mist_level(device: VeSyncBaseDevice, value: float) -> Awaitable[bool]:
    """Set mist level on humidifier."""
    if is_humidifier(device):
        return device.set_mist_level(int(value))
    raise HomeAssistantError("Device does not support mist level adjustment.")


def _fan_oscillation_range(
    device: VeSyncBaseDevice,
) -> tuple[VeSyncFanBase, OscillationRange]:
    """Return the fan and its oscillation range, validating support."""
    if is_fan(device) and (oscillation_range := device.state.oscillation_range):
        return device, oscillation_range
    raise HomeAssistantError("Device does not support oscillation range adjustment.")


async def _set_vertical_oscillation_top(device: VeSyncBaseDevice, value: float) -> bool:
    """Set the top angle of the vertical oscillation range."""
    fan, oscillation_range = _fan_oscillation_range(device)
    if await fan.set_vertical_oscillation_range(
        top=int(value), bottom=oscillation_range.bottom
    ):
        oscillation_range.top = int(value)
        return True
    return False


async def _set_vertical_oscillation_bottom(
    device: VeSyncBaseDevice, value: float
) -> bool:
    """Set the bottom angle of the vertical oscillation range."""
    fan, oscillation_range = _fan_oscillation_range(device)
    if await fan.set_vertical_oscillation_range(
        top=oscillation_range.top, bottom=int(value)
    ):
        oscillation_range.bottom = int(value)
        return True
    return False


async def _set_horizontal_oscillation_left(
    device: VeSyncBaseDevice, value: float
) -> bool:
    """Set the left angle of the horizontal oscillation range."""
    fan, oscillation_range = _fan_oscillation_range(device)
    if await fan.set_horizontal_oscillation_range(
        left=int(value), right=oscillation_range.right
    ):
        oscillation_range.left = int(value)
        return True
    return False


async def _set_horizontal_oscillation_right(
    device: VeSyncBaseDevice, value: float
) -> bool:
    """Set the right angle of the horizontal oscillation range."""
    fan, oscillation_range = _fan_oscillation_range(device)
    if await fan.set_horizontal_oscillation_range(
        left=oscillation_range.left, right=int(value)
    ):
        oscillation_range.right = int(value)
        return True
    return False


def _supports_oscillation_range(device: VeSyncBaseDevice) -> bool:
    """Check if the device supports oscillation range adjustment."""
    return is_fan(device) and device.supports_set_oscillation_range


@dataclass(frozen=True, kw_only=True)
class VeSyncNumberEntityDescription(NumberEntityDescription):
    """Class to describe a Vesync number entity."""

    exists_fn: Callable[[VeSyncBaseDevice], bool] = lambda _: True
    value_fn: Callable[[VeSyncBaseDevice], float]
    native_min_value_fn: Callable[[VeSyncBaseDevice], float]
    native_max_value_fn: Callable[[VeSyncBaseDevice], float]
    set_value_fn: Callable[[VeSyncBaseDevice, float], Awaitable[bool]]


NUMBER_DESCRIPTIONS: list[VeSyncNumberEntityDescription] = [
    VeSyncNumberEntityDescription(
        key="mist_level",
        translation_key="mist_level",
        native_min_value_fn=lambda device: min(_mist_levels(device)),
        native_max_value_fn=lambda device: max(_mist_levels(device)),
        native_step=1,
        mode=NumberMode.SLIDER,
        exists_fn=is_humidifier,
        set_value_fn=_set_mist_level,
        value_fn=lambda device: device.state.mist_virtual_level,
    ),
    VeSyncNumberEntityDescription(
        key="vertical_oscillation_top",
        translation_key="vertical_oscillation_top",
        native_min_value_fn=lambda _: 0,
        native_max_value_fn=lambda _: 180,
        native_step=1,
        native_unit_of_measurement=DEGREE,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        exists_fn=_supports_oscillation_range,
        set_value_fn=_set_vertical_oscillation_top,
        value_fn=lambda device: _fan_oscillation_range(device)[1].top,
    ),
    VeSyncNumberEntityDescription(
        key="vertical_oscillation_bottom",
        translation_key="vertical_oscillation_bottom",
        native_min_value_fn=lambda _: 0,
        native_max_value_fn=lambda _: 180,
        native_step=1,
        native_unit_of_measurement=DEGREE,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        exists_fn=_supports_oscillation_range,
        set_value_fn=_set_vertical_oscillation_bottom,
        value_fn=lambda device: _fan_oscillation_range(device)[1].bottom,
    ),
    VeSyncNumberEntityDescription(
        key="horizontal_oscillation_left",
        translation_key="horizontal_oscillation_left",
        native_min_value_fn=lambda _: 0,
        native_max_value_fn=lambda _: 180,
        native_step=1,
        native_unit_of_measurement=DEGREE,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        exists_fn=_supports_oscillation_range,
        set_value_fn=_set_horizontal_oscillation_left,
        value_fn=lambda device: _fan_oscillation_range(device)[1].left,
    ),
    VeSyncNumberEntityDescription(
        key="horizontal_oscillation_right",
        translation_key="horizontal_oscillation_right",
        native_min_value_fn=lambda _: 0,
        native_max_value_fn=lambda _: 180,
        native_step=1,
        native_unit_of_measurement=DEGREE,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        exists_fn=_supports_oscillation_range,
        set_value_fn=_set_horizontal_oscillation_right,
        value_fn=lambda device: _fan_oscillation_range(device)[1].right,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncBaseDevice]) -> None:
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: DeviceContainer | list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Add number entities."""

    async_add_entities(
        VeSyncNumberEntity(dev, description, coordinator)
        for dev in devices
        for description in NUMBER_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncNumberEntity(VeSyncBaseEntity, NumberEntity):
    """A class to set numeric options on Vesync device."""

    entity_description: VeSyncNumberEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncNumberEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSync number device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    @override
    def native_value(self) -> float:
        """Return the value reported by the number."""
        return self.entity_description.value_fn(self.device)

    @property
    @override
    def native_min_value(self) -> float:
        """Return the value reported by the number."""
        return self.entity_description.native_min_value_fn(self.device)

    @property
    @override
    def native_max_value(self) -> float:
        """Return the value reported by the number."""
        return self.entity_description.native_max_value_fn(self.device)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if not await self.entity_description.set_value_fn(self.device, value):
            raise HomeAssistantError(self.device.last_response.message)
        self.async_write_ha_state()
