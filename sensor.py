from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ADDRESS,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
    HUMIDITY_BYTE_OFFSET,
    MANUFACTURER_ID,
    TEMP_DIVISOR,
    TEMP_HIGH_BYTE_OFFSET,
    TEMP_LOW_BYTE_OFFSET,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lucimed BLE sensor entities from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)

    temperature_sensor = LucimedBLETemperatureSensor(address, name, entry.entry_id)
    humidity_sensor = LucimedBLEHumiditySensor(address, name, entry.entry_id)

    async_add_entities([temperature_sensor, humidity_sensor])

    # ---------------------------------------------------------------
    # Register a PASSIVE BLE callback — no connection needed.
    # HA will call _async_ble_callback every time an advertisement
    # from this device is received.
    # ---------------------------------------------------------------
    @callback
    def _async_ble_callback(
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Parse incoming BLE advertisement and update sensor states."""
        mfr_data: dict[int, bytes] = service_info.manufacturer_data

        if MANUFACTURER_ID not in mfr_data:
            _LOGGER.debug(
                "Manufacturer ID 0x%04X not found in advertisement", MANUFACTURER_ID
            )
            return

        payload: bytes = mfr_data[MANUFACTURER_ID]
        _LOGGER.debug("Raw manufacturer payload: %s", payload.hex(":").upper())

        if len(payload) < 3:
            _LOGGER.warning(
                "Payload too short (%d bytes), expected at least 3", len(payload)
            )
            return

        # ---- Temperature -----------------------------------------------
        # Bytes 0–1: big-endian 16-bit raw value; divide by 10 for °C
        # Example: 0x01 0x1F → 0x011F = 287 → 28.7 °C
        raw_temp: int = (payload[TEMP_HIGH_BYTE_OFFSET] << 8) | payload[
            TEMP_LOW_BYTE_OFFSET
        ]
        temperature: float = raw_temp / TEMP_DIVISOR

        # ---- Humidity --------------------------------------------------
        # Byte 2: unsigned 8-bit percentage value
        # Example: 0x3A = 58 → 58 %
        humidity: int = payload[HUMIDITY_BYTE_OFFSET]

        _LOGGER.debug(
            "Parsed → temperature=%.1f°C, humidity=%d%%", temperature, humidity
        )

        temperature_sensor.update_value(temperature)
        humidity_sensor.update_value(humidity)

    # Store the cancel callback so HA can clean up on unload
    entry.async_on_unload(
        async_register_callback(
            hass,
            _async_ble_callback,
            BluetoothCallbackMatcher(
                address=address,
                connectable=False,  # passive scan only
            ),
            BluetoothScanningMode.PASSIVE,
        )
    )


# ======================================================================
# Entity base class
# ======================================================================


class _LucimedBLEBaseSensor(SensorEntity):
    """Common base for Lucimed BLE sensor entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False  # push-based via BLE callback
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, address: str, device_name: str, entry_id: str) -> None:
        self._address = address
        self._device_name = device_name
        self._entry_id = entry_id
        self._attr_available = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return shared device info so both sensors appear under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=self._device_name,
            manufacturer="Lucimed",
            model="BLE Temperature & Humidity Sensor",
        )

    @callback
    def update_value(self, value: Any) -> None:
        """Receive a new parsed value and schedule a state write."""
        self._attr_native_value = value
        self._attr_available = True
        self.async_write_ha_state()


# ======================================================================
# Temperature entity
# ======================================================================


class LucimedBLETemperatureSensor(_LucimedBLEBaseSensor):
    """Temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_name = "Temperature"

    def __init__(self, address: str, device_name: str, entry_id: str) -> None:
        super().__init__(address, device_name, entry_id)
        # Unique ID ties this entity to the config entry + sensor type
        self._attr_unique_id = f"{address}_temperature"


# ======================================================================
# Humidity entity
# ======================================================================


class LucimedBLEHumiditySensor(_LucimedBLEBaseSensor):
    """Humidity sensor entity."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_name = "Humidity"

    def __init__(self, address: str, device_name: str, entry_id: str) -> None:
        super().__init__(address, device_name, entry_id)
        self._attr_unique_id = f"{address}_humidity"
