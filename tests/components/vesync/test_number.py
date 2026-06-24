"""Tests for the number platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .common import ENTITY_HUMIDIFIER_MIST_LEVEL, mock_devices_response

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_set_mist_level_bad_range(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test set_mist_level invalid value."""
    with (
        pytest.raises(ServiceValidationError),
        patch(
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_mist_level",
            return_value=True,
        ) as method_mock,
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_MIST_LEVEL, ATTR_VALUE: "10"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_not_called()


async def test_set_mist_level(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test set_mist_level usage."""

    with patch(
        "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_mist_level",
        return_value=True,
    ) as method_mock:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_MIST_LEVEL, ATTR_VALUE: "3"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_called_once()


async def test_mist_level(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of mist_level number entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_MIST_LEVEL).state == "6"


@pytest.mark.parametrize(
    ("entity_id", "value", "method", "expected_kwargs"),
    [
        (
            "number.smartpedestalfan_vertical_oscillation_top_angle",
            30,
            "set_vertical_oscillation_range",
            {"top": 30, "bottom": 0},
        ),
        (
            "number.smartpedestalfan_vertical_oscillation_bottom_angle",
            20,
            "set_vertical_oscillation_range",
            {"top": 0, "bottom": 20},
        ),
        (
            "number.smartpedestalfan_horizontal_oscillation_left_angle",
            40,
            "set_horizontal_oscillation_range",
            {"left": 40, "right": 0},
        ),
        (
            "number.smartpedestalfan_horizontal_oscillation_right_angle",
            50,
            "set_horizontal_oscillation_range",
            {"left": 0, "right": 50},
        ),
    ],
)
async def test_set_oscillation_range(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_id: str,
    value: int,
    method: str,
    expected_kwargs: dict[str, int],
) -> None:
    """Test setting the oscillation range of a pedestal fan."""

    mock_devices_response(aioclient_mock, "SmartPedestalFan")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # The range starts at zero as the API does not report current values.
    assert hass.states.get(entity_id).state == "0"

    with patch(
        f"pyvesync.devices.vesyncfan.VeSyncPedestalFan.{method}",
        return_value=True,
    ) as method_mock:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once_with(**expected_kwargs)
    # The newly set value is reflected optimistically.
    assert hass.states.get(entity_id).state == str(value)


async def test_set_oscillation_range_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a failed oscillation range update raises an error."""

    mock_devices_response(aioclient_mock, "SmartPedestalFan")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "number.smartpedestalfan_vertical_oscillation_top_angle"
    with (
        patch(
            "pyvesync.devices.vesyncfan.VeSyncPedestalFan.set_vertical_oscillation_range",
            return_value=False,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 30},
            blocking=True,
        )

    # The value is unchanged after a failed update.
    assert hass.states.get(entity_id).state == "0"
