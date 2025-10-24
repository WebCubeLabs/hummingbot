"""
Lighter Perpetual User Stream Data Source

Extends the spot connector's user stream for perpetual-specific events like positions and funding rates.
"""

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import LighterPerpetualDerivative


class LighterPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """User stream data source for Lighter Perpetual exchange."""
    
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: AuthBase,
        trading_pairs: List[str],
        connector: 'LighterPerpetualDerivative',
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._ws_assistants: List[WSAssistant] = []
        self._connector = connector
        self._current_listen_key = None
        self._listen_for_user_stream_task = None
        self._last_listen_key_ping_ts = None
        self._trading_pairs: List[str] = trading_pairs
        self._auth_token = None
        self._current_backoff = CONSTANTS.INITIAL_BACKOFF

    @property
    def last_recv_time(self) -> float:
        """Get last received time from WebSocket."""
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        """Get or create WebSocket assistant."""
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """Create and connect WebSocket assistant for user stream with exponential backoff."""
        # Get auth token before connecting
        await self._get_auth_token()
        
        ws: WSAssistant = await self._get_ws_assistant()
        url = f"{web_utils.wss_url(self._domain)}"
        
        while True:
            try:
                await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
                self._current_backoff = CONSTANTS.INITIAL_BACKOFF
                self.logger().info(f"Successfully connected to perpetual user stream at {url}")
                safe_ensure_future(self._ping_thread(ws))
                return ws
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "too many" in error_msg or "rate limit" in error_msg:
                    self.logger().warning(
                        f"Rate limit hit when connecting to user stream WebSocket. "
                        f"Backing off for {self._current_backoff} seconds"
                    )
                    await asyncio.sleep(self._current_backoff)
                    self._current_backoff = min(
                        self._current_backoff * CONSTANTS.BACKOFF_MULTIPLIER,
                        CONSTANTS.MAX_BACKOFF
                    )
                    await self._get_auth_token()
                else:
                    raise

    async def _get_auth_token(self):
        """Get authentication token for WebSocket connection."""
        self._auth_token = self._auth.create_auth_token(expiry_seconds=3600)

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """Subscribe to user order, trade, position, and funding rate channels."""
        try:
            account_index = self._auth.account_index
            
            # Subscribe to order updates
            orders_payload = {
                "method": "subscribe",
                "channel": CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
                "account_index": account_index,
            }
            subscribe_orders_request: WSJSONRequest = WSJSONRequest(
                payload=orders_payload,
                is_auth_required=True
            )

            # Subscribe to fills (trades)
            fills_payload = {
                "method": "subscribe",
                "channel": CONSTANTS.USEREVENT_ENDPOINT_NAME,
                "account_index": account_index,
            }
            subscribe_fills_request: WSJSONRequest = WSJSONRequest(
                payload=fills_payload,
                is_auth_required=True
            )
            
            # Subscribe to position updates (perpetual-specific)
            positions_payload = {
                "method": "subscribe",
                "channel": CONSTANTS.POSITION_ENDPOINT_NAME,
                "account_index": account_index,
            }
            subscribe_positions_request: WSJSONRequest = WSJSONRequest(
                payload=positions_payload,
                is_auth_required=True
            )
            
            # Subscribe to funding rate updates (perpetual-specific)
            funding_payload = {
                "method": "subscribe",
                "channel": CONSTANTS.FUNDING_RATE_ENDPOINT_NAME,
            }
            subscribe_funding_request: WSJSONRequest = WSJSONRequest(
                payload=funding_payload,
                is_auth_required=False
            )
            
            await websocket_assistant.send(subscribe_orders_request)
            await websocket_assistant.send(subscribe_fills_request)
            await websocket_assistant.send(subscribe_positions_request)
            await websocket_assistant.send(subscribe_funding_request)

            self.logger().info("Subscribed to perpetual private channels (orders, fills, positions, funding)")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        """Process event message from WebSocket."""
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", event_message.get("error"))
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}"
            })
        elif event_message.get("channel") in [
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USEREVENT_ENDPOINT_NAME,
            CONSTANTS.POSITION_ENDPOINT_NAME,
            CONSTANTS.FUNDING_RATE_ENDPOINT_NAME,
        ]:
            queue.put_nowait(event_message)

    async def _ping_thread(self, websocket_assistant: WSAssistant):
        """Send periodic ping messages to keep connection alive."""
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_TIME_INTERVAL)
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await websocket_assistant.send(ping_request)
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger().exception("Unexpected error while sending ping")
                break

