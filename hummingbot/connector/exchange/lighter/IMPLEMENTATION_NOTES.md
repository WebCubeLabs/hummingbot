# Lighter Exchange Connector Implementation Notes

## Overview

This connector implements integration between Hummingbot and Lighter exchange, following the same architectural pattern as the Hyperliquid connector. Lighter is a decentralized exchange built on zkSync that offers low-fee trading.

## Architecture

The connector follows Hummingbot's standard exchange connector architecture:

```
lighter_exchange.py (Main connector)
├── lighter_auth.py (Authentication & signing)
├── lighter_api_order_book_data_source.py (Market data)
├── lighter_api_user_stream_data_source.py (User events)
├── lighter_order_book.py (Order book messages)
├── lighter_web_utils.py (HTTP/WS utilities)
├── lighter_constants.py (Configuration constants)
└── lighter_utils.py (Config maps & validators)
```

## Key Components

### 1. Authentication (lighter_auth.py)

The authentication system is based on Lighter's SignerClient pattern:

- **API Key Private Key**: Used to sign transactions
- **ETH Private Key**: Account's Ethereum private key
- **Account Index**: Identifies the account on Lighter
- **API Key Index**: Identifies which API key (2-254)
- **Nonce Management**: Thread-safe nonce incrementing per API key

**Important**: The current implementation includes placeholders for SignerClient integration. In production, you need to:
1. Install the Lighter Python SDK: `pip install lighter-python`
2. Compile the SignerClient binary from https://github.com/elliottech/lighter-go
3. Integrate the binary calls in the signing methods

### 2. Order Management

Lighter uses integer-based pricing and amounts:
- Prices and amounts are converted to integers with specific decimal places
- Orders require `client_order_index` for tracking
- Supports multiple order types: LIMIT, MARKET, STOP_LOSS, TAKE_PROFIT, TWAP

### 3. Nonce Management

Each API key maintains its own nonce sequence:
- Nonces must be strictly increasing
- Thread-safe implementation prevents collisions
- Can be synced with API using `/api/v1/nextNonce` endpoint

### 4. Fee Structure

Lighter offers two account types:
- **Standard**: Fee-less (0% maker, 0% taker)
- **Premium**: 0.2 bps maker (0.0002%), 2 bps taker (0.0002%)

The connector defaults to Premium fees for conservative estimation.

## Integration Steps

### Step 1: Install Dependencies

```bash
pip install lighter-python eth-account
```

### Step 2: Setup API Keys

1. Create an API key on Lighter (index 2-254)
2. Get your account index from the API
3. Store your API key private key and ETH private key securely

### Step 3: Configure Hummingbot

Add to `conf_global.yml`:

```yaml
lighter_api_key: "your_api_key_private_key"
lighter_api_secret: "your_eth_private_key"
lighter_account_index: 123  # Your account index
lighter_api_key_index: 2    # Your API key index (2-254)
```

### Step 4: SignerClient Integration

The current implementation requires integration with Lighter's SignerClient binary:

1. **Compile the Signer**:
   ```bash
   git clone https://github.com/elliottech/lighter-go
   cd lighter-go
   just build  # Requires justfile
   ```

2. **Update Auth Methods**:
   In `lighter_auth.py`, update these methods to call the SignerClient binary:
   - `_sign_create_order_params()`
   - `_sign_cancel_order_params()`
   - `_sign_cancel_all_orders_params()`

3. **Auth Token Generation**:
   Implement `create_auth_token_with_expiry()` for WebSocket authentication

## TODO: Production Readiness

### Critical Items

1. **SignerClient Integration** ⚠️
   - [ ] Integrate compiled SignerClient binary
   - [ ] Implement actual transaction signing
   - [ ] Add signature verification

2. **WebSocket Auth** ⚠️
   - [ ] Implement auth token generation
   - [ ] Add token refresh logic
   - [ ] Handle auth failures

3. **Market Data Parsing** ⚠️
   - [ ] Verify order book message format
   - [ ] Test trade message parsing
   - [ ] Validate market ID mappings

4. **Error Handling**
   - [ ] Add retry logic for failed transactions
   - [ ] Handle nonce synchronization errors
   - [ ] Implement rate limit backoff

5. **Testing**
   - [ ] Unit tests for all components
   - [ ] Integration tests with testnet
   - [ ] End-to-end trading tests

### Nice-to-Have Items

- [ ] Support for TWAP orders
- [ ] Advanced order types (stop loss, take profit)
- [ ] Position management for derivatives
- [ ] Historical data fetching
- [ ] Performance optimizations

## API Endpoints Used

| Endpoint | Purpose | Method |
|----------|---------|--------|
| `/api/v1/orderBooks` | Get all markets | GET |
| `/api/v1/orderBookDetails` | Get order book snapshot | GET |
| `/api/v1/sendTx` | Create/cancel orders | POST |
| `/api/v1/sendTxBatch` | Batch operations | POST |
| `/api/v1/nextNonce` | Get next nonce | GET |
| `/api/v1/account` | Get account info | GET |
| `/api/v1/trades` | Get trade history | GET |
| `/api/v1/status` | Health check | GET |

## WebSocket Channels

| Channel | Purpose | Auth Required |
|---------|---------|---------------|
| `orderbook` | Order book updates | No |
| `trades` | Public trades | No |
| `orders` | User order updates | Yes |
| `fills` | User trade fills | Yes |

## Safety Considerations

1. **Private Key Security**: Never log or expose private keys
2. **Nonce Synchronization**: Always fetch current nonce on startup
3. **Rate Limiting**: Respect API rate limits (100 req/min default)
4. **Error Recovery**: Implement graceful degradation on errors
5. **Transaction Verification**: Always verify order status after submission

## References

- [Lighter API Documentation](https://apidocs.lighter.xyz/docs/get-started-for-programmers-1)
- [Lighter Python SDK](https://github.com/elliottech/lighter-python)
- [Lighter Go Signer](https://github.com/elliottech/lighter-go)
- [Hummingbot Connector Development Guide](https://docs.hummingbot.org/)

## Support

For issues or questions:
- Lighter Discord: https://discord.gg/lighter
- Hummingbot Discord: https://discord.gg/hummingbot

## License

This connector follows the same license as Hummingbot (Apache 2.0).

