"""
Lighter Perpetual Authentication

This module reuses the LighterAuth from the spot connector since Lighter uses
the same authentication mechanism for both spot and perpetual trading.
"""

from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth

# Alias for perpetual connector
LighterPerpetualAuth = LighterAuth

__all__ = ["LighterPerpetualAuth"]

