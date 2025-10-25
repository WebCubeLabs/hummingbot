# Lighter Exchange Connector Tests

This directory contains comprehensive tests for the Lighter exchange connector.

## Test Structure

The test suite is organized into two categories:

### 1. Unit Tests
These test individual components in isolation:

- **`test_lighter_auth.py`** - Authentication and SignerClient integration
  - Auth initialization with SignerClient
  - Base URL selection (mainnet/testnet)
  - Nonce incrementing
  - Auth token creation

- **`test_lighter_web_utils.py`** - Web utilities and helper functions
  - REST URL construction
  - WebSocket URL handling
  - Order type conversions
  - Time in force conversions
  - Price/amount formatting and parsing
  - Throttler creation

- **`test_lighter_utils.py`** - Configuration utilities
  - Integer validation with bounds
  - Default fees configuration
  - Config map structure validation

- **`test_lighter_order_book.py`** - Order book message parsing
  - Snapshot message creation
  - Diff message creation
  - Trade message creation

### 2. Integration Tests
These test the full connector using the `test_support` framework:

- **`test_lighter_exchange.py`** - Comprehensive exchange connector tests
  - Extends `AbstractExchangeConnectorTests.ExchangeConnectorTests`
  - Tests all exchange operations: orders, balances, trading rules, etc.
  - Uses mocked API responses to simulate exchange behavior
  - Tests WebSocket event processing
  - Tests error handling and edge cases

## Running Tests

### Run all Lighter tests:
```bash
pytest test/hummingbot/connector/exchange/lighter/ -v
```

### Run only unit tests:
```bash
pytest test/hummingbot/connector/exchange/lighter/test_lighter_auth.py \
       test/hummingbot/connector/exchange/lighter/test_lighter_web_utils.py \
       test/hummingbot/connector/exchange/lighter/test_lighter_utils.py \
       test/hummingbot/connector/exchange/lighter/test_lighter_order_book.py -v
```

### Run only integration tests:
```bash
pytest test/hummingbot/connector/exchange/lighter/test_lighter_exchange.py -v
```

### Run specific test:
```bash
pytest test/hummingbot/connector/exchange/lighter/test_lighter_auth.py::TestLighterAuth::test_auth_initialization -v
```

### Run with coverage:
```bash
pytest test/hummingbot/connector/exchange/lighter/ \
       --cov=hummingbot.connector.exchange.lighter \
       --cov-report=html \
       --cov-report=term
```

### Run with detailed output:
```bash
pytest test/hummingbot/connector/exchange/lighter/ -vv -s
```

## Prerequisites

Install required testing dependencies:

```bash
pip install pytest pytest-asyncio aioresponses lighter-python
```

## Test Coverage

The test suite covers:

✅ **Authentication**
- SignerClient initialization
- Transaction signing
- Auth token generation
- Nonce management

✅ **Web Utilities**
- URL construction (REST & WebSocket)
- Data type conversions
- Price/amount formatting
- Rate limiting

✅ **Configuration**
- Config map validation
- Parameter validation
- Default settings

✅ **Order Book**
- Message parsing
- Snapshot handling
- Diff updates
- Trade events

✅ **Exchange Operations** (Integration)
- Order creation (limit, market, limit maker)
- Order cancellation
- Order status updates
- Balance queries
- Trading rules
- Network status
- WebSocket events
- Error handling

## Mocking Strategy

### Unit Tests
- Use `unittest.mock.patch` to mock `SignerClient`
- Mock individual functions and methods
- Test components in isolation

### Integration Tests
- Use `aioresponses` to mock HTTP requests
- Mock WebSocket connections
- Simulate exchange API responses
- Test full request/response cycles

## Notes

- All tests use mocked `SignerClient` to avoid requiring actual API credentials
- Integration tests require the connector implementation files to be complete
- Tests are independent and don't rely on external state
- WebSocket tests simulate real-time events
- Error cases are tested alongside happy paths

## Adding New Tests

When adding new functionality to the connector:

1. **Add unit tests** for new utility functions or components
2. **Update integration tests** if new API endpoints are added
3. **Add mock responses** for new API response formats
4. **Test error cases** for new operations
5. **Update this README** with new test information

## Continuous Integration

These tests should be run:
- Before committing changes
- In CI/CD pipelines
- Before releasing new versions
- When updating dependencies

## Troubleshooting

### Tests fail with "SignerClient not found"
Ensure `lighter-python` SDK is installed:
```bash
pip install lighter-python
```

### Tests fail with import errors
Ensure all connector files are present and properly structured.

### WebSocket tests timeout
Check that WebSocket mocking is properly configured in the test setup.

### Integration tests fail
Verify that mock responses match the expected API response format.

