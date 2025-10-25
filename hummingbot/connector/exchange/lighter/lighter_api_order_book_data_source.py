import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.lighter import (
    lighter_constants as CONSTANTS,
    lighter_web_utils as web_utils,
)
from hummingbot.connector.exchange.lighter.lighter_order_book import LighterOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange


class LighterAPIOrderBookDataSource(OrderBookTrackerDataSource):
    """Order book data source for Lighter exchange."""
    
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: 'LighterExchange',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory
        self._current_backoff = CONSTANTS.INITIAL_BACKOFF
        self._subscription_count = 0

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None
    ) -> Dict[str, float]:
        """Get last traded prices for trading pairs."""
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Request order book snapshot from Lighter API.
        
        :param trading_pair: Trading pair
        :return: Order book snapshot data
        """
        ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        market_id = self._connector.get_market_id(ex_trading_pair)
        
        params = {
            "market_id": market_id
        }

        data = await self._connector._api_get(
            path_url=CONSTANTS.SNAPSHOT_REST_URL,
            params=params
        )
        return data

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        """
        Create order book snapshot message.
        
        :param trading_pair: Trading pair
        :return: Order book snapshot message
        """
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot.update({"trading_pair": trading_pair})
        snapshot_timestamp: float = snapshot.get('timestamp', 0) / 1000.0
        snapshot_msg: OrderBookMessage = LighterOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Create and connect WebSocket assistant with exponential backoff on rate limit errors.
        
        :return: Connected WebSocket assistant
        """
        url = f"{web_utils.wss_url(self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        
        while True:
            try:
                await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
                # Reset backoff on successful connection
                self._current_backoff = CONSTANTS.INITIAL_BACKOFF
                self.logger().info(f"Successfully connected to {url}")
                return ws
            except Exception as e:
                error_msg = str(e).lower()
                # Check for rate limit errors (HTTP 429 or "too many" messages)
                if "429" in error_msg or "too many" in error_msg or "rate limit" in error_msg:
                    self.logger().warning(
                        f"Rate limit hit when connecting to WebSocket. "
                        f"Backing off for {self._current_backoff} seconds"
                    )
                    await asyncio.sleep(self._current_backoff)
                    # Exponential backoff
                    self._current_backoff = min(
                        self._current_backoff * CONSTANTS.BACKOFF_MULTIPLIER,
                        CONSTANTS.MAX_BACKOFF
                    )
                else:
                    # For non-rate-limit errors, re-raise
                    raise

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribe to trade and order book channels with subscription limit checking.
        
        Lighter limits: 1000 subscriptions per IP
        
        :param ws: WebSocket assistant
        """
        try:
            for trading_pair in self._trading_pairs:
                # Check subscription limit (Lighter allows 1000 subscriptions per IP)
                if self._subscription_count >= CONSTANTS.WS_MAX_SUBSCRIPTIONS:
                    self.logger().warning(
                        f"Approaching WebSocket subscription limit ({CONSTANTS.WS_MAX_SUBSCRIPTIONS}). "
                        "Skipping additional subscriptions."
                    )
                    break
                
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                market_id = self._connector.get_market_id(symbol)
                
                # Subscribe to trades
                trades_payload = {
                    "method": "subscribe",
                    "channel": CONSTANTS.TRADES_ENDPOINT_NAME,
                    "market_id": market_id,
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

                # Subscribe to order book
                order_book_payload = {
                    "method": "subscribe",
                    "channel": CONSTANTS.DEPTH_ENDPOINT_NAME,
                    "market_id": market_id,
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

                await ws.send(subscribe_trade_request)
                self._subscription_count += 1
                
                await ws.send(subscribe_orderbook_request)
                self._subscription_count += 1

                self.logger().info(
                    f"Subscribed to public order book and trade channels for {trading_pair} "
                    f"(Total subscriptions: {self._subscription_count})"
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "too many subscriptions" in error_msg:
                self.logger().error(
                    f"WebSocket subscription limit exceeded. "
                    f"Lighter allows {CONSTANTS.WS_MAX_SUBSCRIPTIONS} subscriptions per IP."
                )
            else:
                self.logger().error("Unexpected error occurred subscribing to order book data streams.", exc_info=True)
            raise

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse order book diff message from WebSocket.
        
        :param raw_message: Raw message from WebSocket
        :param message_queue: Queue to put parsed message
        """
        data = raw_message.get("data", {})
        timestamp: float = data.get("timestamp", 0) / 1000.0
        market_id = data.get("market_id")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(str(market_id))
        
        order_book_message: OrderBookMessage = LighterOrderBook.diff_message_from_exchange(
            data,
            timestamp,
            {"trading_pair": trading_pair}
        )
        message_queue.put_nowait(order_book_message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse order book snapshot message from WebSocket.
        
        :param raw_message: Raw message from WebSocket
        :param message_queue: Queue to put parsed message
        """
        data = raw_message.get("data", {})
        timestamp: float = data.get("timestamp", 0) / 1000.0
        market_id = data.get("market_id")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(str(market_id))
        
        snapshot_message: OrderBookMessage = LighterOrderBook.snapshot_message_from_exchange(
            data,
            timestamp,
            {"trading_pair": trading_pair}
        )
        message_queue.put_nowait(snapshot_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Parse trade message from WebSocket.
        
        :param raw_message: Raw message from WebSocket
        :param message_queue: Queue to put parsed message
        """
        data = raw_message.get("data", {})
        if isinstance(data, list):
            # Multiple trades
            for trade_data in data:
                await self._process_single_trade(trade_data, message_queue)
        else:
            # Single trade
            await self._process_single_trade(data, message_queue)
    
    async def _process_single_trade(self, trade_data: Dict[str, Any], message_queue: asyncio.Queue):
        """
        Process a single trade message.
        
        :param trade_data: Trade data
        :param message_queue: Queue to put parsed message
        """
        market_id = trade_data.get("market_id")
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(str(market_id))
        
        trade_message: OrderBookMessage = LighterOrderBook.trade_message_from_exchange(
            trade_data,
            {"trading_pair": trading_pair}
        )
        message_queue.put_nowait(trade_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        """
        Determine which channel a message came from.
        
        :param event_message: Event message
        :return: Channel identifier
        """
        channel = ""
        if "result" not in event_message:
            channel_name = event_message.get("channel", "")
            if CONSTANTS.DEPTH_ENDPOINT_NAME in channel_name or "orderbook" in channel_name.lower():
                channel = self._diff_messages_queue_key
            elif CONSTANTS.TRADES_ENDPOINT_NAME in channel_name or "trade" in channel_name.lower():
                channel = self._trade_messages_queue_key
        return channel

