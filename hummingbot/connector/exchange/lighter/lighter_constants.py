from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "lighter"
BROKER_ID = "HBOT"
MAX_ORDER_ID_LEN = None

MARKET_ORDER_SLIPPAGE = 0.05

DOMAIN = EXCHANGE_NAME
TESTNET_DOMAIN = "lighter_testnet"

# Lighter API URLs
BASE_URL = "https://mainnet.zklighter.elliot.ai"
TESTNET_BASE_URL = "https://testnet.zklighter.elliot.ai"

# WebSocket URLs (based on SDK documentation)
WS_URL = "wss://mainnet.zklighter.elliot.ai/ws"
TESTNET_WS_URL = "wss://testnet.zklighter.elliot.ai/ws"

# API Endpoints
EXCHANGE_INFO_URL = "/api/v1/orderBooks"
TICKER_PRICE_CHANGE_URL = "/api/v1/orderBooks"
SNAPSHOT_REST_URL = "/api/v1/orderBookDetails"
CREATE_ORDER_URL = "/api/v1/sendTx"
CANCEL_ORDER_URL = "/api/v1/sendTx"
CANCEL_ALL_ORDERS_URL = "/api/v1/sendTxBatch"
ORDER_URL = "/api/v1/order"
ACCOUNT_INFO_URL = "/api/v1/account"
ACCOUNT_TRADE_LIST_URL = "/api/v1/trades"
MY_TRADES_PATH_URL = "/api/v1/trades"
PING_URL = "/api/v1/status"
NEXT_NONCE_URL = "/api/v1/nextNonce"

# WebSocket Channels
TRADES_ENDPOINT_NAME = "trades"
DEPTH_ENDPOINT_NAME = "orderbook"
USER_ORDERS_ENDPOINT_NAME = "orders"
USEREVENT_ENDPOINT_NAME = "fills"

DIFF_EVENT_TYPE = "order_book_snapshot"
TRADE_EVENT_TYPE = "trades"

# Order Types (from Lighter SDK)
ORDER_TYPE_LIMIT = 0
ORDER_TYPE_MARKET = 1
ORDER_TYPE_STOP_LOSS = 2
ORDER_TYPE_STOP_LOSS_LIMIT = 3
ORDER_TYPE_TAKE_PROFIT = 4
ORDER_TYPE_TAKE_PROFIT_LIMIT = 5
ORDER_TYPE_TWAP = 6

# Time in Force (from Lighter SDK)
ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = 0  # IOC
ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 1       # GTT
ORDER_TIME_IN_FORCE_POST_ONLY = 2            # POST_ONLY

# Order Statuses
ORDER_STATE = {
    "open": OrderState.OPEN,
    "pending": OrderState.PENDING_CREATE,
    "filled": OrderState.FILLED,
    "partially_filled": OrderState.PARTIALLY_FILLED,
    "canceled": OrderState.CANCELED,
    "cancelled": OrderState.CANCELED,
    "rejected": OrderState.FAILED,
    "expired": OrderState.CANCELED,
    "failed": OrderState.FAILED,
}

# Account Types
ACCOUNT_TYPE_STANDARD = "standard"  # Fee-less
ACCOUNT_TYPE_PREMIUM = "premium"    # 0.2 bps maker, 2 bps taker

HEARTBEAT_TIME_INTERVAL = 30.0

# Rate Limits (from https://apidocs.lighter.xyz/docs/rate-limits)
# Standard Account: 60 requests/minute
# Premium Account: 24000 weighted requests/minute
# We default to Standard Account limits for safety

# Weighted limits per endpoint
WEIGHT_SEND_TX = 6  # /api/v1/sendTx, /api/v1/sendTxBatch, /api/v1/nextNonce
WEIGHT_INFO = 100  # /, /info
WEIGHT_PUBLIC_DATA = 50  # /api/v1/publicPools, /api/v1/txFromL1TxHash, /api/v1/candlesticks
WEIGHT_ACCOUNT_DATA = 100  # /api/v1/accountInactiveOrders, /api/v1/deposit/latest, /api/v1/pnl
WEIGHT_API_KEYS = 150  # /api/v1/apikeys
WEIGHT_DEFAULT = 300  # Other endpoints

# Standard account limits (conservative)
MAX_REQUEST_PER_MINUTE = 60
ALL_ENDPOINTS_LIMIT = "All"

RATE_LIMITS = [
    # Overall limit for Standard Account
    RateLimit(ALL_ENDPOINTS_LIMIT, limit=MAX_REQUEST_PER_MINUTE, time_interval=60),
    
    # Transaction endpoints (weight: 6)
    RateLimit(limit_id=CREATE_ORDER_URL, limit=10, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_SEND_TX)]),
    RateLimit(limit_id=CANCEL_ORDER_URL, limit=10, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_SEND_TX)]),
    RateLimit(limit_id=CANCEL_ALL_ORDERS_URL, limit=10, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_SEND_TX)]),
    RateLimit(limit_id=NEXT_NONCE_URL, limit=10, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_SEND_TX)]),
    
    # Info endpoints (weight: 100)
    RateLimit(limit_id=PING_URL, limit=1, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_INFO)]),
    
    # Public data endpoints (weight: 50)
    RateLimit(limit_id=EXCHANGE_INFO_URL, limit=1, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_PUBLIC_DATA)]),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_URL, limit=1, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_PUBLIC_DATA)]),
    
    # Account data endpoints (weight: 100)
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=1, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_ACCOUNT_DATA)]),
    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=1, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_ACCOUNT_DATA)]),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=1, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_ACCOUNT_DATA)]),
    
    # Order book snapshot (weight: 300)
    RateLimit(limit_id=SNAPSHOT_REST_URL, limit=1, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)]),
    
    # Order status (weight: 300)
    RateLimit(limit_id=ORDER_URL, limit=1, time_interval=60,
              linked_limits=[LinkedLimitWeightPair(ALL_ENDPOINTS_LIMIT, weight=WEIGHT_DEFAULT)]),
]

# WebSocket Limits (per IP)
WS_MAX_SESSIONS = 100
WS_MAX_SUBSCRIPTIONS = 1000
WS_MAX_UNIQUE_ACCOUNTS = 10

# Transaction Type Constants (from Lighter API)
TX_TYPE_L2_CHANGE_PUB_KEY = 8
TX_TYPE_L2_CREATE_SUB_ACCOUNT = 9
TX_TYPE_L2_CREATE_PUBLIC_POOL = 10
TX_TYPE_L2_UPDATE_PUBLIC_POOL = 11
TX_TYPE_L2_TRANSFER = 12
TX_TYPE_L2_WITHDRAW = 13
TX_TYPE_L2_CREATE_ORDER = 14
TX_TYPE_L2_CANCEL_ORDER = 15
TX_TYPE_L2_CANCEL_ALL_ORDERS = 16
TX_TYPE_L2_MODIFY_ORDER = 17
TX_TYPE_L2_MINT_SHARES = 18
TX_TYPE_L2_BURN_SHARES = 19
TX_TYPE_L2_UPDATE_LEVERAGE = 20

# Transaction Status
TX_STATUS_FAILED = 0
TX_STATUS_PENDING = 1
TX_STATUS_EXECUTED = 2
TX_STATUS_PENDING_FINAL = 3

# Reconnect backoff settings
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 60.0  # seconds
BACKOFF_MULTIPLIER = 2.0

ORDER_NOT_EXIST_MESSAGE = "order not found"
UNKNOWN_ORDER_MESSAGE = "Order does not exist"

