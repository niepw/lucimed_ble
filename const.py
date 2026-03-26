DOMAIN = "lucimed_ble"

# BLE Manufacturer ID (Company ID 0x0901, little-endian in raw adv = 01 09)
MANUFACTURER_ID = 0x0901  # decimal 2305

# Offsets within manufacturer payload (bytes AFTER the 2-byte company ID)
# Raw adv payload after company ID: [01, 1F, 3A, ED, 68, 00, ED, 5E, 9B]
TEMP_HIGH_BYTE_OFFSET = 0   # 0x01
TEMP_LOW_BYTE_OFFSET  = 1   # 0x1F  → combined 0x011F = 287 → 28.7 °C
HUMIDITY_BYTE_OFFSET  = 2   # 0x3A  = 58 %

TEMP_DIVISOR = 10.0  # raw value / 10 = actual °C

CONF_ADDRESS = "address"
CONF_NAME    = "name"
DEFAULT_NAME = "Lucimed BLE Sensor"
