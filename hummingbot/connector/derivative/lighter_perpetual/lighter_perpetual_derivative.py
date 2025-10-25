import asyncio
import hashlib
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source import (
    LighterPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_user_stream_data_source import (
    LighterPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterPerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

bpm_logger = None


class LighterPerpetualDerivative(PerpetualDerivativePyBase):
    """
    Lighter Perpetual Derivative connector for Hummingbot.
    
    This connector integrates with Lighter's perpetual contracts API using the Lighter Python SDK.
    Lighter is a decentralized exchange built on zkSync offering perpetual trading.
    """
    
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        lighter_perpetual_api_key: str = None,
        lighter_perpetual_api_secret: str = None,
        lighter_perpetual_account_index: int = None,
        lighter_perpetual_api_key_index: int = 2,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        """
        Initialize Lighter perpetual derivative connector.
        
        :param lighter_perpetual_api_key: API key private key
        :param lighter_perpetual_api_secret: ETH private key
        :param lighter_perpetual_account_index: Account index on Lighter
        :param lighter_perpetual_api_key_index: API key index (2-254)
        :param trading_pairs: List of trading pairs to trade
        :param trading_required: Whether trading is required
        :param domain: Domain (lighter_perpetual or lighter_perpetual_testnet)
        """
        self.lighter_perpetual_api_key = lighter_perpetual_api_key
        self.lighter_perpetual_api_secret = lighter_perpetual_api_secret
        self.lighter_perpetual_account_index = lighter_perpetual_account_index
        self.lighter_perpetual_api_key_index = lighter_perpetual_api_key_index
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        
        # Market ID mappings
        self.market_id_to_symbol: Dict[int, str] = {}
        self.symbol_to_market_id: Dict[str, int] = {}
        
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        """Exchange name (lighter_perpetual or lighter_perpetual_testnet)."""
        return self._domain

    @property
    def authenticator(self) -> Optional[LighterPerpetualAuth]:
        """Get authenticator instance."""
        if self._trading_required:
            return LighterPerpetualAuth(
                api_key=self.lighter_perpetual_api_key,
                api_secret=self.lighter_perpetual_api_secret,
                account_index=self.lighter_perpetual_account_index,
                api_key_index=self.lighter_perpetual_api_key_index,
                use_testnet=(self._domain == CONSTANTS.TESTNET_DOMAIN),
            )
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        """Get rate limits for this connector."""
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        """Get the domain (mainnet/testnet)."""
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        """Maximum length of client order ID."""
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        """Prefix for client order IDs."""
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        """Path for trading rules request."""
        return CONSTANTS.MARKETS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        """Path for trading pairs request."""
        return CONSTANTS.MARKETS_URL

    @property
    def check_network_request_path(self) -> str:
        """Path for network check request."""
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

    @property
    def funding_fee_poll_interval(self) -> int:
        """Funding fee polling interval in seconds."""
        return 120

    async def _make_network_check_request(self):
        """Make a network connectivity check request."""
        await self._api_get(path_url=self.check_network_request_path)

    def supported_order_types(self) -> List[OrderType]:
        """Get supported order types."""
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self):
        """Get supported position modes."""
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        """Get the collateral token for buy orders."""
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        """Get the collateral token for sell orders."""
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        """Check if request exception is related to time synchronization."""
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        """Create web assistants factory."""
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth)

    async def _make_trading_rules_request(self) -> Any:
        """Make request for trading rules."""
        return await self._api_get(path_url=self.trading_rules_request_path)

    async def _make_trading_pairs_request(self) -> Any:
        """Make request for trading pairs."""
        return await self._api_get(path_url=self.trading_pairs_request_path)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        """Check if exception indicates order not found during status update."""
        return "not found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        """Check if exception indicates order not found during cancellation."""
        return "not found" in str(cancelation_exception).lower()

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """Quantize order price according to trading rules."""
        d_price = Decimal(round(float(f"{price:.5g}"), 6))
        return d_price

    async def _update_trading_rules(self):
        """Update trading rules from the exchange."""
        exchange_info = await self._make_trading_rules_request()
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _initialize_trading_pair_symbol_map(self):
        """Initialize trading pair symbol map."""
        try:
            exchange_info = await self._make_trading_pairs_request()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        """Create order book data source."""
        return LighterPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        """Create user stream data source."""
        return LighterPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _status_polling_loop_fetch_updates(self):
        """Fetch updates in the status polling loop."""
        await safe_gather(
            self._update_trade_history(),
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_order_status(self):
        """Update order statuses."""
        await self._update_orders()

    async def _update_lost_orders_status(self):
        """Update lost orders status."""
        await self._update_lost_orders()

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        """Get fee for a trade."""
        is_maker = is_maker or False
        fee = build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
        return fee

    async def _update_trading_fees(self):
        """Update trading fees information from the exchange."""
        pass

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """Cancel an order."""
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        market_id = self.symbol_to_market_id.get(symbol)
        
        if market_id is None:
            raise ValueError(f"Market ID not found for symbol {symbol}")

        cancel_result = await self._api_delete(
            path_url=CONSTANTS.CANCEL_ORDER_URL.format(order_id=order_id),
            is_auth_required=True,
        )

        if cancel_result.get("success"):
            return True
        else:
            error_msg = cancel_result.get("error", "Unknown error")
            self.logger().debug(f"The order {order_id} does not exist on Lighter Perpetuals. "
                              f"No cancellation needed. Error: {error_msg}")
            await self._order_tracker.process_order_not_found(order_id)
            raise IOError(f"Order cancellation failed: {error_msg}")

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        """Create a buy order."""
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(trading_pair, reference_price * Decimal(1 + CONSTANTS.MARKET_ORDER_SLIPPAGE))

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        """Create a sell order."""
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        md5 = hashlib.md5()
        md5.update(order_id.encode('utf-8'))
        hex_order_id = f"0x{md5.hexdigest()}"
        
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(trading_pair, reference_price * Decimal(1 - CONSTANTS.MARKET_ORDER_SLIPPAGE))

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=hex_order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return hex_order_id

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:
        """Place an order on the exchange."""
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        market_id = self.symbol_to_market_id.get(symbol)
        
        if market_id is None:
            raise ValueError(f"Market ID not found for symbol {symbol}")

        order_side = "buy" if trade_type is TradeType.BUY else "sell"
        
        # Determine order type
        if order_type is OrderType.LIMIT_MAKER:
            order_type_str = "limit_maker"
        elif order_type is OrderType.MARKET:
            order_type_str = "market"
        else:
            order_type_str = "limit"

        api_params = {
            "market_id": market_id,
            "side": order_side,
            "type": order_type_str,
            "size": str(amount),
            "price": str(price),
            "client_order_id": order_id,
            "reduce_only": position_action == PositionAction.CLOSE,
        }
        
        order_result = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=api_params,
            is_auth_required=True)
        
        if not order_result.get("success"):
            raise IOError(f"Error submitting order {order_id}: {order_result.get('error')}")
        
        exchange_order_id = order_result["data"]["order_id"]
        return (exchange_order_id, self.current_timestamp)

    async def _update_trade_history(self):
        """Update trade history from the exchange."""
        orders = list(self._order_tracker.all_fillable_orders.values())
        if len(orders) == 0:
            return
        
        try:
            trades_response = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_LIST_URL,
                is_auth_required=True)
            
            if trades_response.get("success"):
                for trade in trades_response.get("data", []):
                    self._process_trade_event_message(trade)
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            self.logger().warning(
                f"Failed to fetch trade updates. Error: {request_error}",
                exc_info=request_error,
            )

    def _process_trade_event_message(self, trade: Dict[str, Any]):
        """Process trade event message."""
        exchange_order_id = str(trade.get("order_id"))
        fillable_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        
        if fillable_order is not None:
            fee_asset = fillable_order.quote_asset
            position_action = PositionAction.OPEN if trade.get("reduce_only") is False else PositionAction.CLOSE
            
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(str(trade.get("fee", 0))), token=fee_asset)]
            )

            trade_update = TradeUpdate(
                trade_id=str(trade["trade_id"]),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=fillable_order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(str(trade["size"])),
                fill_quote_amount=Decimal(str(trade["price"])) * Decimal(str(trade["size"])),
                fill_price=Decimal(str(trade["price"])),
                fill_timestamp=trade.get("timestamp", self.current_timestamp),
            )

            self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        """Get all trade updates for an order."""
        # Use _update_trade_history instead
        pass

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """Request order status from the exchange."""
        try:
            if tracked_order.exchange_order_id:
                exchange_order_id = tracked_order.exchange_order_id
            else:
                exchange_order_id = await tracked_order.get_exchange_order_id()
        except asyncio.TimeoutError:
            raise IOError(f"Timeout waiting for exchange order ID for {tracked_order.client_order_id}")
        
        order_response = await self._api_get(
            path_url=CONSTANTS.ORDER_URL.format(order_id=exchange_order_id),
            is_auth_required=True)
        
        if not order_response.get("success"):
            raise IOError(f"Error fetching order status: {order_response.get('error')}")
        
        order_data = order_response["data"]
        current_state = order_data["status"]
        
        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_data.get("updated_at", self.current_timestamp),
            new_state=CONSTANTS.ORDER_STATUS_MAP.get(current_state, current_state),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_data["order_id"]),
        )
        return order_update

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        """Iterate over user event queue."""
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Lighter. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        """Listen to user stream events."""
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    event_type = event_message.get("type")
                    data = event_message.get("data")
                    
                    if event_type == "order":
                        self._process_order_message(data)
                    elif event_type == "trade":
                        await self._process_trade_message(data)
                    elif event_type == "position":
                        # Position updates handled in _update_positions
                        pass
                elif event_message is asyncio.CancelledError:
                    raise asyncio.CancelledError
                else:
                    raise Exception(event_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _process_trade_message(self, trade: Dict[str, Any]):
        """Process trade message from WebSocket."""
        exchange_order_id = str(trade.get("order_id"))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
            self.logger().debug(f"Ignoring trade message for unknown order {exchange_order_id}")
            return

        position_action = PositionAction.OPEN if trade.get("reduce_only") is False else PositionAction.CLOSE
        fee_asset = tracked_order.quote_asset
        
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=Decimal(str(trade.get("fee", 0))), token=fee_asset)]
        )
        
        trade_update = TradeUpdate(
            trade_id=str(trade["trade_id"]),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=trade.get("timestamp", self.current_timestamp),
            fill_price=Decimal(str(trade["price"])),
            fill_base_amount=Decimal(str(trade["size"])),
            fill_quote_amount=Decimal(str(trade["price"])) * Decimal(str(trade["size"])),
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """Process order message from WebSocket."""
        client_order_id = order_msg.get("client_order_id")
        if not client_order_id:
            return
        
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message for unknown order {client_order_id}")
            return
        
        current_state = order_msg["status"]
        exchange_order_id = str(order_msg["order_id"])
        tracked_order.update_exchange_order_id(exchange_order_id)
        
        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_msg.get("updated_at", self.current_timestamp),
            new_state=CONSTANTS.ORDER_STATUS_MAP.get(current_state, current_state),
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _format_trading_rules(self, exchange_info: Dict) -> List[TradingRule]:
        """Format trading rules from exchange info."""
        return_val: list = []
        
        markets = exchange_info.get("data", {}).get("markets", [])
        
        for market in markets:
            try:
                symbol = market["symbol"]
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)
                
                # Store market ID mapping
                market_id = market["market_id"]
                self.market_id_to_symbol[market_id] = symbol
                self.symbol_to_market_id[symbol] = market_id
                
                step_size = Decimal(str(market.get("size_increment", "0.001")))
                price_size = Decimal(str(market.get("price_increment", "0.01")))
                min_order_size = Decimal(str(market.get("min_order_size", "0.001")))
                collateral_token = market.get("quote_currency", "USDC")
                
                return_val.append(
                    TradingRule(
                        trading_pair,
                        min_base_amount_increment=step_size,
                        min_price_increment=price_size,
                        min_order_size=min_order_size,
                        buy_order_collateral_token=collateral_token,
                        sell_order_collateral_token=collateral_token,
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule for {market}. Skipping.",
                                  exc_info=True)
        return return_val

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict):
        """Initialize trading pair symbols from exchange info."""
        mapping = bidict()
        markets = exchange_info.get("data", {}).get("markets", [])
        
        for market in markets:
            try:
                symbol = market["symbol"]
                base = market["base_currency"]
                quote = market["quote_currency"]
                trading_pair = combine_to_hb_trading_pair(base, quote)
                
                if trading_pair in mapping.inverse:
                    self._resolve_trading_pair_symbols_duplicate(mapping, symbol, base, quote)
                else:
                    mapping[symbol] = trading_pair
            except Exception:
                self.logger().error(f"Error parsing market {market}. Skipping.", exc_info=True)
        
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        """Get last traded price for a trading pair."""
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        market_id = self.symbol_to_market_id.get(symbol)
        
        if market_id is None:
            raise ValueError(f"Market ID not found for symbol {symbol}")
        
        response = await self._api_get(
            path_url=CONSTANTS.TICKER_PRICE_URL.format(market_id=market_id))
        
        if response.get("success"):
            return float(response["data"]["last_price"])
        return 0.0

    def _resolve_trading_pair_symbols_duplicate(self, mapping: bidict, new_exchange_symbol: str, base: str, quote: str):
        """Resolve duplicate trading pair symbols."""
        expected_exchange_symbol = f"{base}-{quote}"
        trading_pair = combine_to_hb_trading_pair(base, quote)
        current_exchange_symbol = mapping.inverse[trading_pair]
        
        if current_exchange_symbol == expected_exchange_symbol:
            pass
        elif new_exchange_symbol == expected_exchange_symbol:
            mapping.pop(current_exchange_symbol)
            mapping[new_exchange_symbol] = trading_pair
        else:
            self.logger().error(
                f"Could not resolve the exchange symbols {new_exchange_symbol} and {current_exchange_symbol}")
            mapping.pop(current_exchange_symbol)

    async def _update_balances(self):
        """Update account balances."""
        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INFO_URL,
            is_auth_required=True)
        
        if account_info.get("success"):
            balances = account_info["data"].get("balances", {})
            for currency, balance_data in balances.items():
                total_balance = Decimal(str(balance_data.get("total", 0)))
                available_balance = Decimal(str(balance_data.get("available", 0)))
                
                self._account_balances[currency] = total_balance
                self._account_available_balances[currency] = available_balance

    async def _update_positions(self):
        """Update position information."""
        positions_response = await self._api_get(
            path_url=CONSTANTS.POSITION_INFORMATION_URL,
            is_auth_required=True)
        
        if not positions_response.get("success"):
            return
        
        positions = positions_response["data"].get("positions", [])
        
        for position_data in positions:
            try:
                market_id = position_data["market_id"]
                symbol = self.market_id_to_symbol.get(market_id)
                if not symbol:
                    continue
                
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
                
                size = Decimal(str(position_data.get("size", 0)))
                if size == 0:
                    continue
                
                position_side = PositionSide.LONG if size > 0 else PositionSide.SHORT
                unrealized_pnl = Decimal(str(position_data.get("unrealized_pnl", 0)))
                entry_price = Decimal(str(position_data.get("entry_price", 0)))
                leverage = Decimal(str(position_data.get("leverage", 1)))
                
                pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
                
                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=abs(size),
                    leverage=leverage
                )
                self._perpetual_trading.set_position(pos_key, position)
            except Exception:
                self.logger().error(f"Error parsing position {position_data}. Skipping.", exc_info=True)
        
        # Remove positions that are no longer active
        if not positions:
            keys = list(self._perpetual_trading.account_positions.keys())
            for key in keys:
                self._perpetual_trading.remove_position(key)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        """Get the current position mode."""
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        """Set position mode for a trading pair."""
        msg = ""
        success = True
        initial_mode = await self._get_position_mode()
        if initial_mode != mode:
            msg = "Lighter only supports the ONEWAY position mode."
            success = False
        return success, msg

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        """Set leverage for a trading pair."""
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        market_id = self.symbol_to_market_id.get(symbol)
        
        if market_id is None:
            return False, f"Market ID not found for {trading_pair}"
        
        try:
            params = {
                "market_id": market_id,
                "leverage": leverage,
            }
            
            set_leverage_response = await self._api_post(
                path_url=CONSTANTS.SET_LEVERAGE_URL,
                data=params,
                is_auth_required=True)
            
            if set_leverage_response.get("success"):
                return True, ""
            else:
                return False, f"Unable to set leverage: {set_leverage_response.get('error')}"
        except Exception as exception:
            return False, f"There was an error setting the leverage for {trading_pair} ({exception})"

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        """Fetch last funding fee payment for a trading pair."""
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        market_id = self.symbol_to_market_id.get(symbol)
        
        if market_id is None:
            return 0, Decimal("-1"), Decimal("-1")
        
        try:
            funding_response = await self._api_get(
                path_url=CONSTANTS.FUNDING_INFO_URL.format(market_id=market_id),
                is_auth_required=True)
            
            if funding_response.get("success"):
                funding_data = funding_response["data"]
                timestamp = funding_data.get("timestamp", 0)
                funding_rate = Decimal(str(funding_data.get("funding_rate", 0)))
                payment = Decimal(str(funding_data.get("payment", 0)))
                return timestamp, funding_rate, payment
        except Exception as e:
            self.logger().warning(f"Error fetching funding info: {e}")
        
        return 0, Decimal("-1"), Decimal("-1")

