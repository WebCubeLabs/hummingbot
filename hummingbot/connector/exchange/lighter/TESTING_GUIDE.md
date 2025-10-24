# Lighter Exchange Connector - Testing Guide

## Overview

This guide explains how to test the Lighter exchange connector (both spot and perpetual) using Hummingbot's testing framework.

## Test Structure

Tests follow the same pattern as other exchange connectors (e.g., Hyperliquid). Each component has its own test file:

### Spot Connector Tests
Location: `test/hummingbot/connector/exchange/lighter/`

1. `test_lighter_auth.py` - Authentication and signing tests
2. `test_lighter_web_utils.py` - Web utilities tests
3. `test_lighter_utils.py` - Configuration and utility tests
4. `test_lighter_order_book.py` - Order book message parsing tests
5. `test_lighter_api_order_book_data_source.py` - Market data source tests
6. `test_lighter_user_stream_data_source.py` - User stream tests
7. `test_lighter_exchange.py` - Main exchange connector tests

### Perpetual Connector Tests
Location: `test/hummingbot/connector/derivative/lighter_perpetual/`

1. `test_lighter_perpetual_auth.py` - Perpetual authentication tests
2. `test_lighter_perpetual_web_utils.py` - Perpetual web utilities tests
3. `test_lighter_perpetual_utils.py` - Perpetual configuration tests
4. `test_lighter_perpetual_order_book.py` - Perpetual order book tests
5. `test_lighter_perpetual_api_order_book_data_source.py` - Perpetual market data tests
6. `test_lighter_perpetual_user_stream_data_source.py` - Perpetual user stream tests
7. `test_lighter_perpetual_derivative.py` - Main perpetual connector tests

## Running Tests

### Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install lighter-python
   pip install pytest pytest-asyncio aioresponses
   ```

2. **Set Environment Variables** (for integration tests):
   ```bash
   export LIGHTER_API_KEY="your_api_key_private_key"
   export LIGHTER_API_SECRET="your_eth_private_key"
   export LIGHTER_ACCOUNT_INDEX="your_account_index"
   export LIGHTER_API_KEY_INDEX="2"
   ```

### Unit Tests

Run unit tests for specific components:

```bash
# Test spot connector auth
pytest test/hummingbot/connector/exchange/lighter/test_lighter_auth.py -v

# Test spot connector exchange
pytest test/hummingbot/connector/exchange/lighter/test_lighter_exchange.py -v

# Test perpetual connector
pytest test/hummingbot/connector/derivative/lighter_perpetual/test_lighter_perpetual_derivative.py -v

# Run all Lighter tests
pytest test/hummingbot/connector/exchange/lighter/ -v
pytest test/hummingbot/connector/derivative/lighter_perpetual/ -v
```

### Integration Tests

Integration tests require actual API credentials and will make real API calls:

```bash
# Run integration tests (requires credentials)
pytest test/hummingbot/connector/exchange/lighter/test_lighter_exchange.py::TestLighterExchangeIntegration -v
```

## Test Example: Basic Spot Exchange Test

Create `test/hummingbot/connector/exchange/lighter/test_lighter_exchange.py`:

```python
import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange
from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.core.data_type.common import OrderType, TradeType


class LighterExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "test_api_key_private_key"
        cls.api_secret = "test_eth_private_key"
        cls.account_index = 123
        cls.api_key_index = 2
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
    
    def setUp(self) -> None:
        super().setUp()
        self.exchange = LighterExchange(
            lighter_api_key=self.api_key,
            lighter_api_secret=self.api_secret,
            lighter_account_index=self.account_index,
            lighter_api_key_index=self.api_key_index,
            trading_pairs=[self.trading_pair],
        )
    
    @property
    def all_symbols_url(self):
        return f"{CONSTANTS.BASE_URL}{CONSTANTS.EXCHANGE_INFO_URL}"
    
    @property
    def latest_prices_url(self):
        return f"{CONSTANTS.BASE_URL}{CONSTANTS.TICKER_PRICE_CHANGE_URL}"
    
    @property
    def network_status_url(self):
        return f"{CONSTANTS.BASE_URL}{CONSTANTS.PING_URL}"
    
    @property
    def trading_rules_url(self):
        return f"{CONSTANTS.BASE_URL}{CONSTANTS.EXCHANGE_INFO_URL}"
    
    @property
    def order_creation_url(self):
        return f"{CONSTANTS.BASE_URL}{CONSTANTS.CREATE_ORDER_URL}"
    
    @property
    def balance_url(self):
        return f"{CONSTANTS.BASE_URL}{CONSTANTS.ACCOUNT_INFO_URL}"
    
    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.MARKET, supported_types)
        self.assertIn(OrderType.LIMIT_MAKER, supported_types)
    
    @aioresponses()
    def test_check_network_success(self, mock_api):
        mock_api.get(self.network_status_url, status=200, body=json.dumps({"status": "ok"}))
        
        result = self.async_run_with_timeout(self.exchange.check_network())
        
        self.assertEqual(result, NetworkStatus.CONNECTED)
    
    @aioresponses()
    def test_create_order(self, mock_api):
        # Mock order creation response
        order_response = {
            "status": "success",
            "order_index": "12345",
            "timestamp": 1234567890000
        }
        mock_api.post(self.order_creation_url, status=200, body=json.dumps(order_response))
        
        # Create order
        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1.0"),
            order_type=OrderType.LIMIT,
            price=Decimal("2000.0")
        )
        
        self.assertIsNotNone(order_id)


if __name__ == "__main__":
    unittest.main()
```

## Manual Testing

### 1. Test Authentication

```python
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth

# Initialize auth
auth = LighterAuth(
    api_key="your_api_key_private_key",
    api_secret="your_eth_private_key",
    account_index=123,
    api_key_index=2,
    use_testnet=True  # Use testnet for testing
)

# Test auth token generation
token = auth.create_auth_token(expiry_seconds=3600)
print(f"Auth token: {token}")
```

### 2. Test Order Creation

```python
import asyncio
from decimal import Decimal
from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange

async def test_order():
    exchange = LighterExchange(
        lighter_api_key="your_api_key",
        lighter_api_secret="your_secret",
        lighter_account_index=123,
        lighter_api_key_index=2,
        trading_pairs=["ETH-USDC"],
        domain="lighter_testnet"  # Use testnet
    )
    
    # Place a limit order
    order_id = exchange.buy(
        trading_pair="ETH-USDC",
        amount=Decimal("0.01"),
        order_type=OrderType.LIMIT,
        price=Decimal("2000.0")
    )
    
    print(f"Order created: {order_id}")

asyncio.run(test_order())
```

### 3. Test WebSocket Connection

```python
import asyncio
from hummingbot.connector.exchange.lighter.lighter_api_order_book_data_source import LighterAPIOrderBookDataSource
from hummingbot.connector.exchange.lighter import lighter_web_utils as web_utils

async def test_websocket():
    api_factory = web_utils.build_api_factory()
    data_source = LighterAPIOrderBookDataSource(
        trading_pairs=["ETH-USDC"],
        connector=None,  # Mock connector
        api_factory=api_factory,
        domain="lighter_testnet"
    )
    
    # Test WebSocket connection
    ws = await data_source._connected_websocket_assistant()
    print(f"WebSocket connected: {ws is not None}")

asyncio.run(test_websocket())
```

## Testing Checklist

### Spot Connector
- [ ] Authentication with Lighter SDK
- [ ] Order creation (limit, market, maker)
- [ ] Order cancellation
- [ ] Balance fetching
- [ ] Trading rules loading
- [ ] Order book data streaming
- [ ] User stream (orders, fills)
- [ ] Rate limit handling
- [ ] Reconnect logic
- [ ] Error handling

### Perpetual Connector
- [ ] All spot connector tests
- [ ] Position management
- [ ] Leverage setting
- [ ] Funding rate fetching
- [ ] PnL calculations
- [ ] Liquidation price calculations
- [ ] Position updates via WebSocket
- [ ] Funding rate updates via WebSocket

## Common Issues and Solutions

### Issue 1: ImportError for lighter SDK
**Solution**: Install the Lighter Python SDK
```bash
pip install lighter-python
```

### Issue 2: Authentication Errors
**Solution**: Verify your API keys and account index
- Check that API_KEY_PRIVATE_KEY is correct
- Verify ETH_PRIVATE_KEY is valid
- Confirm ACCOUNT_INDEX matches your Lighter account
- Ensure API_KEY_INDEX is between 2-254

### Issue 3: Rate Limit Errors
**Solution**: The connector has built-in rate limiting and exponential backoff
- Standard account: 60 requests/minute
- Premium account: 24,000 weighted requests/minute
- Wait for backoff period if rate limited

### Issue 4: WebSocket Connection Failures
**Solution**: Check network connectivity and subscription limits
- Max 100 WebSocket sessions per IP
- Max 1000 subscriptions per IP
- Max 10 unique accounts per IP

## Continuous Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Test Lighter Connectors
  run: |
    pytest test/hummingbot/connector/exchange/lighter/ -v
    pytest test/hummingbot/connector/derivative/lighter_perpetual/ -v
```

## Next Steps

1. **Create test files** for each component
2. **Write unit tests** with mocked responses
3. **Write integration tests** with real API (testnet)
4. **Add to CI/CD pipeline**
5. **Document test results**

## Resources

- [Lighter API Documentation](https://apidocs.lighter.xyz/docs/get-started-for-programmers-1)
- [Lighter Python SDK](https://github.com/elliottech/lighter-python)
- [Hummingbot Testing Guide](https://docs.hummingbot.org/developers/connectors/test/)
- [pytest Documentation](https://docs.pytest.org/)
- [aioresponses Documentation](https://github.com/pnuckowski/aioresponses)

