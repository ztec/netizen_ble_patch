"""Connection settings shared by setup and configuration flows."""

import re
from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_AUTO_SYNC_TIME,
    CONF_USE_VERIFICATION_CODE,
    CONF_VERIFICATION_CODE,
    DEFAULT_VERIFICATION_CODE,
)


def connection_settings(values: Mapping[str, Any]) -> dict[str, Any]:
    """Keep verification opt-in, including for entries created by upstream."""
    enabled = values.get(CONF_USE_VERIFICATION_CODE, False)
    code = (values.get(CONF_VERIFICATION_CODE) or DEFAULT_VERIFICATION_CODE).strip().upper()
    if enabled and not re.fullmatch(r"[0-9A-F]{8}", code):
        raise ValueError("Verification requires exactly eight hexadecimal digits")
    return {
        CONF_USE_VERIFICATION_CODE: enabled,
        CONF_VERIFICATION_CODE: code,
        CONF_AUTO_SYNC_TIME: values.get(CONF_AUTO_SYNC_TIME, False),
    }


def verification_code(values: Mapping[str, Any]) -> str | None:
    """Return no family ID unless the user explicitly enabled verification."""
    settings = connection_settings(values)
    return settings[CONF_VERIFICATION_CODE] if settings[CONF_USE_VERIFICATION_CODE] else None
