"""Constants for Pet Netizen BLE integration (feeder-only, uses petnetizen_feeder library)."""

DOMAIN = "netizen_ble"

CONF_ADDRESS = "address"
CONF_VERIFICATION_CODE = "verification_code"
CONF_DEVICE_TYPE = "device_type"
CONF_USE_VERIFICATION_CODE = "use_verification_code"
CONF_AUTO_SYNC_TIME = "auto_sync_time"

# BLE service UUIDs (standard, JK, ALI - petnetizen_feeder protocol)
SERVICE_UUID = "0000ae30-0000-1000-8000-00805f9b34fb"
SERVICE_UUIDS = (
    "0000ae30-0000-1000-8000-00805f9b34fb",  # standard feeder / water / litter
    "0000fff0-0000-1000-8000-00805f9b34fb",  # JK feeder
    "0000ffff-0000-1000-8000-00805f9b34fb",  # ALI feeder
    "0000ae00-0000-1000-8000-00805f9b34fb",  # Call Pet + Aurora Cat/Teaser
)

# Default verification code (no cloud required)
DEFAULT_VERIFICATION_CODE = "00000000"

# Name prefixes for discovery (aligned with petnetizen_feeder FEEDER_NAME_PREFIXES)
SUPPORTED_BLE_NAME_PREFIXES = ("Du", "JK", "ALI", "PET", "FEED", "AURORA", "TC")
