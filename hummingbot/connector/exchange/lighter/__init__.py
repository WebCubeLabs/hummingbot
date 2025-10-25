"""
Lighter Exchange Connector for Hummingbot

This connector integrates Lighter exchange (https://lighter.xyz) with Hummingbot trading bot.
Lighter is a decentralized exchange built on zkSync with low fees and high performance.

Key Features:
- Standard account: Fee-less trading (0% maker, 0% taker)
- Premium account: 0.2 bps maker, 2 bps taker fees
- Direct integration with Lighter Python SDK (SignerClient)
- WebSocket support with exponential backoff reconnect logic
- Rate limit aware (60 req/min standard, 24000 weighted req/min premium)
- Support for multiple order types (limit, market, stop loss, take profit, TWAP)

Configuration Requirements:
- lighter_api_key: API key private key (API_KEY_PRIVATE_KEY)
- lighter_api_secret: Ethereum wallet private key (ETH_PRIVATE_KEY)
- lighter_account_index: Account index on Lighter (ACCOUNT_INDEX)
- lighter_api_key_index: API key index (2-254, default: 2)

For more information, visit:
- API Documentation: https://apidocs.lighter.xyz/docs/get-started-for-programmers-1
- SDK Repository: https://github.com/elliottech/lighter-python
- Rate Limits: https://apidocs.lighter.xyz/docs/rate-limits
- Data Structures: https://apidocs.lighter.xyz/docs/data-structures-constants-and-errors
"""

from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.connector.exchange.lighter.lighter_api_order_book_data_source import LighterAPIOrderBookDataSource
from hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source import LighterAPIUserStreamDataSource
from hummingbot.connector.exchange.lighter.lighter_order_book import LighterOrderBook

__all__ = [
    "LighterExchange",
    "LighterAuth",
    "LighterAPIOrderBookDataSource",
    "LighterAPIUserStreamDataSource",
    "LighterOrderBook",
]

