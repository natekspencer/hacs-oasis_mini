"""Helpers for the Oasis Mini integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

from .pyoasismini import OasisMini


def create_client(data: dict[str, Any]) -> OasisMini:
    """Create a Oasis Mini local client."""
    return OasisMini(data[CONF_HOST], data.get(CONF_ACCESS_TOKEN))
