"""Tests for the fan module."""

from contextlib import nullcontext
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pyvesync.base_devices import VeSyncFanBase
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import ATTR_PRESET_MODE, DOMAIN as FAN_DOMAIN
from homeassistant.components.vesync.fan import VeSyncFanHA
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_FAN, mock_devices_response

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

NoException = nullcontext()


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_fan_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(aioclient_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == FAN_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, "pyvesync.devices.vesyncfan.VeSyncTowerFan.turn_on"),
        (SERVICE_TURN_OFF, "pyvesync.devices.vesyncfan.VeSyncTowerFan.turn_off"),
    ],
)
async def test_turn_on_off_success(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    action: str,
    command: str,
) -> None:
    """Test turn_on and turn_off method."""

    mock_devices_response(aioclient_mock, "SmartTowerFan")

    with (
        patch(command, new_callable=AsyncMock, return_value=True) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.async_write_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                action,
                {ATTR_ENTITY_ID: ENTITY_FAN},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (
            SERVICE_TURN_ON,
            "pyvesync.base_devices.vesyncbasedevice.VeSyncBaseToggleDevice.turn_on",
        ),
        (
            SERVICE_TURN_OFF,
            "pyvesync.base_devices.vesyncbasedevice.VeSyncBaseToggleDevice.turn_off",
        ),
    ],
)
async def test_turn_on_off_raises_error(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    action: str,
    command: str,
) -> None:
    """Test turn_on and turn_off raises errors when fails."""

    # returns False indicating failure in which case raises HomeAssistantError.
    with (
        patch(
            command,
            return_value=False,
        ) as method_mock,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            action,
            {ATTR_ENTITY_ID: ENTITY_FAN},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
@pytest.mark.parametrize(
    ("preset_mode", "patch_target"),
    [
        ("normal", "pyvesync.devices.vesyncfan.VeSyncTowerFan.set_normal_mode"),
        (
            "sleep",
            "pyvesync.devices.vesyncfan.VeSyncTowerFan.set_sleep_mode",
        ),
        ("turbo", "pyvesync.devices.vesyncfan.VeSyncTowerFan.set_turbo_mode"),
        ("auto", "pyvesync.devices.vesyncfan.VeSyncTowerFan.set_auto_mode"),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
    preset_mode: str,
    patch_target: str,
) -> None:
    """Test set_preset_mode method via turn on for test coverage."""

    # If VeSyncTowerFan.mode fails (returns False), then HomeAssistantError is raised
    with (
        expectation,
        patch(
            patch_target,
            return_value=api_response,
        ) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.async_write_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: ENTITY_FAN, ATTR_PRESET_MODE: preset_mode},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()


def _mock_fan_device(*, modes: list[str], mode: str, fan_level: int | None) -> Mock:
    """Build a mock VeSync fan device for direct entity testing."""
    return Mock(
        VeSyncFanBase,
        cid="fan",
        device_name="Test Fan",
        device_type="LPF-R432S-AEU",
        current_firm_version="1.0.0",
        sub_device_no=0,
        is_on=True,
        modes=modes,
        fan_levels=list(range(1, 13)),
        set_mode=AsyncMock(return_value=True),
        state=Mock(mode=mode, fan_level=fan_level, oscillation_status=None),
    )


@pytest.mark.parametrize(
    ("mode", "fan_level", "expected"),
    [
        pytest.param("manual", 1, 8, id="manual_lowest"),
        pytest.param("normal", 12, 100, id="normal_highest"),
        pytest.param("normal", 0, 0, id="off"),
        pytest.param("normal", -1, None, id="out_of_range"),
        pytest.param("normal", None, None, id="missing"),
        pytest.param("auto", 6, None, id="non_speed_mode"),
    ],
)
def test_percentage(mode: str, fan_level: int | None, expected: int | None) -> None:
    """Test percentage handles out-of-range/missing fan levels without raising."""
    device = _mock_fan_device(
        modes=["normal", "manual"], mode=mode, fan_level=fan_level
    )
    fan = VeSyncFanHA(device, Mock())

    assert fan.percentage == expected


async def test_set_preset_mode_eco() -> None:
    """Test the eco preset is exposed and sets the mode via set_mode."""
    device = _mock_fan_device(modes=["normal", "eco"], mode="eco", fan_level=-1)
    fan = VeSyncFanHA(device, Mock())

    assert "eco" in fan.preset_modes
    assert fan.preset_mode == "eco"

    with patch.object(fan, "async_write_ha_state"):
        await fan.async_set_preset_mode("eco")

    device.set_mode.assert_awaited_once_with("eco")


@pytest.mark.parametrize(
    ("action", "command"),
    [
        ("true", "pyvesync.devices.vesyncfan.VeSyncTowerFan.toggle_oscillation"),
        ("false", "pyvesync.devices.vesyncfan.VeSyncTowerFan.toggle_oscillation"),
    ],
)
@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
async def test_oscillation_success(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    action: str,
    command: str,
    api_response: bool,
    expectation,
) -> None:
    """Test oscillation on and off."""

    mock_devices_response(aioclient_mock, "SmartTowerFan")

    with (
        expectation,
        patch(
            command, new_callable=AsyncMock, return_value=api_response
        ) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.async_write_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                "oscillate",
                {ATTR_ENTITY_ID: ENTITY_FAN, "oscillating": action},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()
