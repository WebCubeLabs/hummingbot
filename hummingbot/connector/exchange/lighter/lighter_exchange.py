import asyncio
import hashlib
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.lighter import (
    lighter_constants as CONSTANTS,
    lighter_web_utils as web_utils,
)
from hummingbot.connector.exchange.lighter.lighter_api_order_book_data_source import (
    LighterAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source import (
    LighterAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterExchange(ExchangePyBase):
    """
    Lighter Exchange connector for Hummingbot.
    
    Lighter is a decentralized exchange built on zkSync with low fees.
    This connector integrates with Lighter's API using the Lighter Python SDK.
    """
    
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        lighter_api_key: str = None,
        lighter_api_secret: str = None,
        lighter_account_index: int = None,
        lighter_api_key_index: int = 2,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        """
        Initialize Lighter exchange connector.
        
        :param lighter_api_key: API key private key (API_KEY_PRIVATE_KEY)
        :param lighter_api_secret: ETH private key
        :param lighter_account_index: Account index on Lighter
        :param lighter_api_key_index: API key index (2-254)
        :param trading_pairs: List of trading pairs to trade
        :param trading_required: Whether trading is required
        :param domain: Domain (lighter or lighter_testnet)
        """
        self.lighter_api_key = lighter_api_key
        self.lighter_api_secret = lighter_api_secret
        self.lighter_account_index = lighter_account_index
        self.lighter_api_key_index = lighter_api_key_index
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp = None
        self._last_trades_poll_timestamp = 1.0
        
        # Market ID mappings
        self.market_id_to_symbol: Dict[int, str] = {}
        self.symbol_to_market_id: Dict[str, int] = {}
        
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        """Exchange name (lighter or lighter_testnet)."""
        return self._domain

    @property
    def authenticator(self) -> Optional[LighterAuth]:
        """Get authenticator instance."""
        if self._trading_required:
            return LighterAuth(
                api_key=self.lighter_api_key,
                api_secret=self.lighter_api_secret,
                account_index=self.lighter_account_index,
                api_key_index=self.lighter_api_key_index,
                use_testnet=(self._domain == CONSTANTS.TESTNET_DOMAIN)
            )
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        """Get rate limit rules."""
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        """Get domain."""
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        """Max length for client order ID."""
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        """Prefix for client order IDs."""
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        """Path for trading rules request."""
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        """Path for trading pairs request."""
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        """Path for network check."""
        return CONSTANTS.PING_URL

    @property
    def trading_pairs(self):
        """Get trading pairs."""
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        """Whether cancel requests are synchronous."""
        return True

    @property
    def is_trading_required(self) -> bool:
        """Whether trading is required."""
        return self._trading_required

    def get_market_id(self, symbol: str) -> int:
        """
        Get market ID for a symbol.
        
        :param symbol: Trading symbol
        :return: Market ID
        """
        return self.symbol_to_market_id.get(symbol, 0)

    async def _make_network_check_request(self):
        """Make network check request."""
        await self._api_get(path_url=self.check_network_request_path)

    def supported_order_types(self) -> List[OrderType]:
        """
        Get supported order types.
        
        :return: List of supported OrderType
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        """
        Get prices for all trading pairs.
        
        :return: List of price dictionaries
        """
        res = []
        try:
            response = await self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_URL)
            
            # Parse Lighter API response for market prices
            if isinstance(response, list):
                for market in response:
                    result = {
                        "symbol": market.get("symbol", ""),
                        "price": str(market.get("last_price", "0"))
                    }
                    res.append(result)
        except Exception:
            self.logger().exception("Error fetching all pairs prices")
        
        return res

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        """Check if exception is related to time synchronization."""
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        """Create web assistants factory."""
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth
        )

    async def _make_trading_rules_request(self) -> Any:
        """
        Make request for trading rules.
        
        :return: Exchange info response
        """
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        """
        Make request for trading pairs.
        
        :return: Exchange info response
        """
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)
        return exchange_info

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """Check if error is order not found."""
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """Check if cancelation error is order not found."""
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Quantize order price according to trading rules.
        
        :param trading_pair: Trading pair
        :param price: Price to quantize
        :return: Quantized price
        """
        d_price = Decimal(round(float(f"{price:.5g}"), 6))
        return d_price

    async def _update_trading_rules(self):
        """Update trading rules from exchange."""
        try:
            exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
            trading_rules_list = await self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("Error updating trading rules")

    async def _initialize_trading_pair_symbol_map(self):
        """Initialize trading pair symbol mappings."""
        try:
            exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        """Create order book data source."""
        return LighterAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        """Create user stream data source."""
        return LighterAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None
    ) -> TradeFeeBase:
        """
        Calculate trading fee.
        
        Lighter fees:
        - Standard account: 0% maker, 0% taker
        - Premium account: 0.02% maker, 0.2% taker
        
        :return: TradeFeeBase object
        """
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        fee = DeductedFromReturnsTradeFee(
            percent=self.estimate_fee_pct(is_maker),
            flat_fees=[TokenAmount(amount=Decimal("0"), token=quote_currency)]
        )
        return fee

    async def _update_balances(self):
        """Update account balances."""
        try:
            account_info = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_INFO_URL,
                params={"account_index": self.lighter_account_index}
            )
            
            self._account_available_balances.clear()
            self._account_balances.clear()
            
            # Parse Lighter account response
            if isinstance(account_info, dict):
                balances = account_info.get("balances", {})
                for asset, balance_info in balances.items():
                    total_balance = Decimal(str(balance_info.get("total", "0")))
                    available_balance = Decimal(str(balance_info.get("available", "0")))
                    
                    self._account_balances[asset] = total_balance
                    self._account_available_balances[asset] = available_balance
        except Exception:
            self.logger().exception("Error updating balances")
            raise

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        """
        Initialize trading pair symbol mappings from exchange info.
        
        :param exchange_info: Exchange information
        """
        self._set_trading_pair_symbol_map(bidict())
        
        if isinstance(exchange_info, list):
            for market_info in exchange_info:
                try:
                    market_id = market_info.get("market_id")
                    symbol = market_info.get("symbol", "")
                    
                    # Store market ID mappings
                    self.market_id_to_symbol[market_id] = symbol
                    self.symbol_to_market_id[symbol] = market_id
                    
                    # Create Hummingbot trading pair format
                    base = market_info.get("base_asset", "")
                    quote = market_info.get("quote_asset", "")
                    trading_pair = combine_to_hb_trading_pair(base, quote)
                    
                    self._trading_pair_symbol_map[trading_pair] = symbol
                except Exception:
                    self.logger().exception(f"Error parsing market info: {market_info}")

    async def _format_trading_rules(self, exchange_info: List) -> List[TradingRule]:
        """
        Format trading rules from exchange info.
        
        :param exchange_info: Exchange information
        :return: List of TradingRule objects
        """
        trading_rules = []
        
        if isinstance(exchange_info, list):
            for market_info in exchange_info:
                try:
                    symbol = market_info.get("symbol", "")
                    base = market_info.get("base_asset", "")
                    quote = market_info.get("quote_asset", "")
                    trading_pair = combine_to_hb_trading_pair(base, quote)
                    
                    min_order_size = Decimal(str(market_info.get("min_order_size", "0.001")))
                    min_price_increment = Decimal(str(market_info.get("tick_size", "0.01")))
                    min_base_amount_increment = Decimal(str(market_info.get("step_size", "0.001")))
                    
                    trading_rule = TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=min_price_increment,
                        min_base_amount_increment=min_base_amount_increment,
                    )
                    trading_rules.append(trading_rule)
                except Exception:
                    self.logger().exception(f"Error parsing trading rule: {market_info}")
        
        return trading_rules

    async def _update_time_synchronizer(self):
        """Update time synchronizer (not needed for Lighter)."""
        pass

    async def _update_order_fills_from_trades(self):
        """Update order fills from trades."""
        # Lighter provides fills via WebSocket, so this may not be needed
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """
        Get all trade updates for an order.
        
        :param order: InFlightOrder to get trades for
        :return: List of TradeUpdate objects
        """
        trade_updates = []
        
        try:
            if order.exchange_order_id:
                trades_response = await self._api_get(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params={
                        "account_index": self.lighter_account_index,
                        "order_index": order.exchange_order_id
                    }
                )
                
                if isinstance(trades_response, list):
                    for trade in trades_response:
                        trade_update = self._parse_trade_update(trade, order)
                        if trade_update:
                            trade_updates.append(trade_update)
        except Exception:
            self.logger().exception(f"Error fetching trades for order {order.client_order_id}")
        
        return trade_updates

    def _parse_trade_update(self, trade_data: Dict[str, Any], order: InFlightOrder) -> Optional[TradeUpdate]:
        """
        Parse trade data into TradeUpdate.
        
        :param trade_data: Trade data from API
        :param order: Associated order
        :return: TradeUpdate object or None
        """
        try:
            trade_id = str(trade_data.get("trade_id", ""))
            price = Decimal(str(trade_data.get("price", "0")))
            size = Decimal(str(trade_data.get("size", "0")))
            fee_amount = Decimal(str(trade_data.get("fee", "0")))
            
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=order.trade_type,
                percent_token=order.quote_asset,
                flat_fees=[TokenAmount(amount=fee_amount, token=order.quote_asset)]
            )
            
            trade_update = TradeUpdate(
                trade_id=trade_id,
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                fee=fee,
                fill_base_amount=size,
                fill_quote_amount=size * price,
                fill_price=price,
                fill_timestamp=trade_data.get("timestamp", 0) / 1000.0,
            )
            
            return trade_update
        except Exception:
            self.logger().exception(f"Error parsing trade update: {trade_data}")
            return None

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Request order status from exchange.
        
        :param tracked_order: Order to check status for
        :return: OrderUpdate object
        """
        try:
            order_response = await self._api_get(
                path_url=CONSTANTS.ORDER_URL,
                params={
                    "account_index": self.lighter_account_index,
                    "order_index": tracked_order.exchange_order_id
                }
            )
            
            order_status = order_response.get("status", "")
            new_state = CONSTANTS.ORDER_STATE.get(order_status, tracked_order.current_state)
            
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=order_response.get("timestamp", 0) / 1000.0,
                new_state=new_state,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
            )
            
            return order_update
        except Exception:
            self.logger().exception(f"Error requesting order status for {tracked_order.client_order_id}")
            raise

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        """
        Place an order on Lighter exchange.
        
        :param order_id: Client order ID
        :param trading_pair: Trading pair
        :param amount: Order amount
        :param trade_type: BUY or SELL
        :param order_type: Order type
        :param price: Order price
        :return: Tuple of (exchange_order_id, timestamp)
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        market_id = self.get_market_id(symbol)
        
        # Convert to Lighter order type
        lighter_order_type = CONSTANTS.ORDER_TYPE_LIMIT
        lighter_tif = CONSTANTS.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME
        
        if order_type == OrderType.MARKET:
            lighter_order_type = CONSTANTS.ORDER_TYPE_MARKET
            lighter_tif = CONSTANTS.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL
        elif order_type == OrderType.LIMIT_MAKER:
            lighter_tif = CONSTANTS.ORDER_TIME_IN_FORCE_POST_ONLY
        
        # Convert price and amount to integers for Lighter
        price_int = web_utils.format_price_for_lighter(float(price))
        amount_int = web_utils.format_amount_for_lighter(float(amount))
        
        # Generate client order index from order_id
        client_order_index = int(hashlib.md5(order_id.encode()).hexdigest()[:16], 16) % (2**63)
        
        api_params = {
            "market_id": market_id,
            "is_buy": trade_type == TradeType.BUY,
            "base_amount": amount_int,
            "price": price_int,
            "order_type": lighter_order_type,
            "time_in_force": lighter_tif,
            "client_order_index": client_order_index,
        }
        
        order_result = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=api_params,
            is_auth_required=True
        )
        
        if order_result.get("status") == "error":
            raise IOError(f"Error submitting order {order_id}: {order_result.get('message')}")
        
        exchange_order_id = str(order_result.get("order_index", ""))
        timestamp = order_result.get("timestamp", self.current_timestamp * 1000) / 1000.0
        
        return (exchange_order_id, timestamp)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Cancel an order on Lighter exchange.
        
        :param order_id: Client order ID
        :param tracked_order: Order to cancel
        """
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        market_id = self.get_market_id(symbol)
        
        api_params = {
            "market_id": market_id,
            "order_index": tracked_order.exchange_order_id,
        }
        
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=api_params,
            is_auth_required=True
        )
        
        if cancel_result.get("status") == "error":
            error_msg = cancel_result.get("message", "")
            if CONSTANTS.ORDER_NOT_EXIST_MESSAGE in error_msg:
                self.logger().debug(f"Order {order_id} does not exist on Lighter. No cancellation needed.")
                await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"Error cancelling order {order_id}: {error_msg}")
        
        return True

    async def _user_stream_event_listener(self):
        """
        Listen to user stream events and process them.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message.get("channel", "")
                
                if channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                    # Order update
                    self._process_order_message(event_message.get("data", {}))
                elif channel == CONSTANTS.USEREVENT_ENDPOINT_NAME:
                    # Trade fill
                    await self._process_trade_message(event_message.get("data", {}))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Process order update message.
        
        :param order_msg: Order message from WebSocket
        """
        try:
            client_order_index = order_msg.get("client_order_index")
            # Find tracked order by client_order_index
            tracked_order = None
            for order in self._order_tracker.all_updatable_orders.values():
                if hasattr(order, 'client_order_index') and order.client_order_index == client_order_index:
                    tracked_order = order
                    break
            
            if not tracked_order:
                self.logger().debug(f"Ignoring order message: order not tracked")
                return
            
            order_status = order_msg.get("status", "")
            new_state = CONSTANTS.ORDER_STATE.get(order_status, tracked_order.current_state)
            
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=order_msg.get("timestamp", 0) / 1000.0,
                new_state=new_state,
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(order_msg.get("order_index", "")),
            )
            
            self._order_tracker.process_order_update(order_update=order_update)
        except Exception:
            self.logger().exception("Error processing order message")

    async def _process_trade_message(self, trade_msg: Dict[str, Any]):
        """
        Process trade fill message.
        
        :param trade_msg: Trade message from WebSocket
        """
        try:
            order_index = str(trade_msg.get("order_index", ""))
            tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(order_index)
            
            if not tracked_order:
                self.logger().debug(f"Ignoring trade message: order {order_index} not tracked")
                return
            
            trade_update = self._parse_trade_update(trade_msg, tracked_order)
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)
        except Exception:
            self.logger().exception("Error processing trade message")

