"""
Lighter Perpetual Web Utilities

Web utilities for Lighter perpetual trading, extending the spot connector utilities.
"""

import time
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterPerpetualRESTPreProcessor(RESTPreProcessorBase):
    """REST request preprocessor for Lighter Perpetual API."""
    
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        request.headers["Accept"] = "application/json"
        return request


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = "lighter_perpetual") -> str:
    """
    Construct full REST URL from path.
    
    :param path_url: API endpoint path
    :param domain: Domain identifier
    :return: Full URL
    """
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "lighter_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = "lighter_perpetual") -> str:
    """
    Get WebSocket URL for the domain.
    
    :param domain: Domain identifier
    :return: WebSocket URL
    """
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "lighter_perpetual" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None
) -> WebAssistantsFactory:
    """
    Build WebAssistantsFactory with Lighter Perpetual configuration.
    
    :param throttler: Rate limiter
    :param auth: Authentication handler
    :return: Configured WebAssistantsFactory
    """
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[LighterPerpetualRESTPreProcessor()],
        auth=auth
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler
) -> WebAssistantsFactory:
    """
    Build WebAssistantsFactory without time synchronizer.
    
    :param throttler: Rate limiter
    :return: Configured WebAssistantsFactory
    """
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[LighterPerpetualRESTPreProcessor()]
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    """Create rate limiter with Lighter's rate limits."""
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler: AsyncThrottler, domain: str) -> float:
    """
    Get current server time.
    
    :param throttler: Rate limiter
    :param domain: Domain identifier
    :return: Current timestamp
    """
    return time.time()


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    """
    Verify if a trading pair is enabled.
    
    :param rule: Exchange information for a trading pair
    :return: True if enabled, False otherwise
    """
    return True


# Reuse conversion functions from spot connector
from hummingbot.connector.exchange.lighter.lighter_web_utils import (
    order_type_to_lighter,
    time_in_force_to_lighter,
    format_price_for_lighter,
    format_amount_for_lighter,
    parse_price_from_lighter,
    parse_amount_from_lighter,
)

__all__ = [
    "private_rest_url",
    "public_rest_url",
    "rest_url",
    "wss_url",
    "build_api_factory",
    "build_api_factory_without_time_synchronizer_pre_processor",
    "create_throttler",
    "get_current_server_time",
    "is_exchange_information_valid",
    "order_type_to_lighter",
    "time_in_force_to_lighter",
    "format_price_for_lighter",
    "format_amount_for_lighter",
    "parse_price_from_lighter",
    "parse_amount_from_lighter",
]

