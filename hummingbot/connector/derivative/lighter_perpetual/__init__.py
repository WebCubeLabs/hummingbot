"""
Lighter Perpetual Derivative Connector for Hummingbot

This connector integrates Lighter perpetual contracts with Hummingbot trading bot.
Lighter is a decentralized exchange built on zkSync offering both spot and perpetual trading.

Key Features for Perpetuals:
- Leverage trading (up to configurable leverage)
- Funding rate mechanisms
- Position management (long/short)
- Standard account: Fee-less trading (0% maker, 0% taker)
- Premium account: 0.2 bps maker, 2 bps taker fees
- Direct integration with Lighter Python SDK (SignerClient)
- WebSocket support with exponential backoff reconnect logic
- Rate limit aware (60 req/min standard, 24000 weighted req/min premium)

Configuration Requirements:
- lighter_perpetual_api_key: API key private key (API_KEY_PRIVATE_KEY)
- lighter_perpetual_api_secret: Ethereum wallet private key (ETH_PRIVATE_KEY)
- lighter_perpetual_account_index: Account index on Lighter (ACCOUNT_INDEX)
- lighter_perpetual_api_key_index: API key index (2-254, default: 2)

For more information, visit:
- API Documentation: https://apidocs.lighter.xyz/docs/get-started-for-programmers-1
- SDK Repository: https://github.com/elliottech/lighter-python
- Rate Limits: https://apidocs.lighter.xyz/docs/rate-limits
- Data Structures: https://apidocs.lighter.xyz/docs/data-structures-constants-and-errors

Note: This connector reuses authentication and utilities from the spot connector
(hummingbot.connector.exchange.lighter) as Lighter uses the same API infrastructure
for both spot and perpetual trading.
"""

__all__ = [
    "LighterPerpetualDerivative",
]

