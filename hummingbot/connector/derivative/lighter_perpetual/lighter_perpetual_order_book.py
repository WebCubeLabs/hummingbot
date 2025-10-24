"""
Lighter Perpetual Order Book

Reuses the order book implementation from the spot connector since
the message format is the same for both spot and perpetual markets.
"""

from hummingbot.connector.exchange.lighter.lighter_order_book import LighterOrderBook

# Alias for perpetual connector
LighterPerpetualOrderBook = LighterOrderBook

__all__ = ["LighterPerpetualOrderBook"]

