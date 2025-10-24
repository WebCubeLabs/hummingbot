# Lighter Perpetual Derivative Connector Tests

This directory contains comprehensive tests for the Lighter perpetual derivative connector.

## Test Structure

The test suite is organized into two categories:

### 1. Unit Tests
These test individual components in isolation:

- **`test_lighter_perpetual_auth.py`** - Authentication (reuses spot auth)
  - Verifies that perpetual auth is an alias for spot auth
  - Tests initialization with perpetual-specific config

- **`test_lighter_perpetual_web_utils.py`** - Web utilities
  - REST URL construction for perpetuals
  - WebSocket URL handling
  - Reuses spot conversion functions
  - Throttler creation

- **`test_lighter_perpetual_utils.py`** - Configuration utilities
  - Default fees for perpetuals
  - Config map structure validation
  - Perpetual-specific settings

### 2. Integration Tests
These test the full derivative connector using the `test_support` framework:

- **`test_lighter_perpetual_derivative.py`** - Comprehensive derivative connector tests
  - Extends `AbstractPerpetualDerivativeTests.PerpetualDerivativeTests`
  - Tests all derivative operations: orders, positions, funding, etc.
  - Uses mocked API responses to simulate exchange behavior
  - Tests WebSocket event processing
  - Tests position management
  - Tests funding rate and payments
  - Tests error handling and edge cases

## Running Tests

### Run all Lighter perpetual tests:
```bash
pytest test/hummingbot/connector/derivative/lighter_perpetual/ -v
```

### Run only unit tests:
```bash
pytest test/hummingbot/connector/derivative/lighter_perpetual/test_lighter_perpetual_auth.py \
       test/hummingbot/connector/derivative/lighter_perpetual/test_lighter_perpetual_web_utils.py \
       test/hummingbot/connector/derivative/lighter_perpetual/test_lighter_perpetual_utils.py -v
```

### Run only integration tests:
```bash
pytest test/hummingbot/connector/derivative/lighter_perpetual/test_lighter_perpetual_derivative.py -v
```

### Run specific test:
```bash
pytest test/hummingbot/connector/derivative/lighter_perpetual/test_lighter_perpetual_derivative.py::LighterPerpetualDerivativeTests::test_create_order -v
```

### Run with coverage:
```bash
pytest test/hummingbot/connector/derivative/lighter_perpetual/ \
       --cov=hummingbot.connector.derivative.lighter_perpetual \
       --cov-report=html \
       --cov-report=term
```

### Run both spot and perpetual tests:
```bash
pytest test/hummingbot/connector/exchange/lighter/ \
       test/hummingbot/connector/derivative/lighter_perpetual/ -v
```

## Prerequisites

Install required testing dependencies:

```bash
pip install pytest pytest-asyncio aioresponses lighter-python pandas
```

## Test Coverage

The test suite covers:

✅ **Authentication**
- SignerClient initialization (shared with spot)
- Transaction signing for perpetual orders
- Auth token generation
- Nonce management

✅ **Web Utilities**
- URL construction (REST & WebSocket)
- Data type conversions
- Price/amount formatting
- Rate limiting

✅ **Configuration**
- Perpetual-specific config maps
- Parameter validation
- Default settings

✅ **Derivative Operations** (Integration)
- Order creation (limit, market, limit maker)
- Order cancellation
- Order status updates
- Position management
  - Opening positions
  - Closing positions
  - Position updates via WebSocket
- Leverage management
- Funding rates
  - Funding rate queries
  - Funding payment tracking
- Balance queries (collateral)
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
- Mock position and funding events

## Key Differences from Spot Tests

The perpetual derivative tests include additional coverage for:

1. **Position Management**
   - Long/short positions
   - Position mode (one-way vs hedge)
   - Unrealized PnL tracking
   - Leverage settings

2. **Funding Mechanism**
   - Funding rate queries
   - Funding payment tracking
   - Next funding time

3. **Collateral Management**
   - Margin requirements
   - Initial and maintenance margin
   - Liquidation thresholds

4. **Position-Specific Events**
   - Position update WebSocket events
   - Funding payment events
   - Liquidation events

## Notes

- All tests use mocked `SignerClient` to avoid requiring actual API credentials
- Integration tests require the connector implementation files to be complete
- Tests are independent and don't rely on external state
- WebSocket tests simulate real-time position and funding events
- Error cases are tested alongside happy paths
- Perpetual tests reuse spot authentication logic

## Adding New Tests

When adding new functionality to the perpetual connector:

1. **Add unit tests** for new utility functions or components
2. **Update integration tests** if new API endpoints are added
3. **Add mock responses** for new API response formats
4. **Test position-related operations** thoroughly
5. **Test funding mechanism** if funding-related changes are made
6. **Update this README** with new test information

## Continuous Integration

These tests should be run:
- Before committing changes
- In CI/CD pipelines
- Before releasing new versions
- When updating dependencies
- Alongside spot connector tests

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

### Position tests fail
Ensure position management logic is properly implemented in the connector.

### Funding tests fail
Verify funding rate and payment endpoints are correctly mocked.

