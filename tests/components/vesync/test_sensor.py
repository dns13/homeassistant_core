"""Tests for the sensor module."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    ALL_DEVICE_NAMES,
    ENTITY_FAN_SLEEP_PREFERENCE,
    ENTITY_FAN_TEMPERATURE,
    ENTITY_HUMIDIFIER_HUMIDITY,
    mock_devices_response,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_sensor_state(
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
        if entity.domain == SENSOR_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


async def test_humidity(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of humidity sensor entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_HUMIDITY).state == "35"


async def test_fan_temperature(
    hass: HomeAssistant, fan_config_entry: MockConfigEntry
) -> None:
    """Test the state of the fan temperature sensor entity."""

    # 72 °F reported by the device converted to the metric test system (°C).
    assert hass.states.get(ENTITY_FAN_TEMPERATURE).state == "22.2222222222222"


async def test_fan_sleep_preference_type(
    hass: HomeAssistant, fan_config_entry: MockConfigEntry
) -> None:
    """Test the state of the fan sleep preference type sensor entity."""

    assert hass.states.get(ENTITY_FAN_SLEEP_PREFERENCE).state == "1"
