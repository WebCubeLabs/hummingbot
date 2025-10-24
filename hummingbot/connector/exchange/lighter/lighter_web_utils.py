import time
from typing import Any, Dict, Optional

import hummingbot.connector.exchange.lighter.lighter_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterRESTPreProcessor(RESTPreProcessorBase):
    """REST request preprocessor for Lighter API."""
    
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


def rest_url(path_url: str, domain: str = "lighter") -> str:
    """
    Construct full REST URL from path.
    
    :param path_url: API endpoint path
    :param domain: Domain identifier (lighter or lighter_testnet)
    :return: Full URL
    """
    base_url = CONSTANTS.BASE_URL if domain == "lighter" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = "lighter") -> str:
    """
    Get WebSocket URL for the domain.
    
    :param domain: Domain identifier (lighter or lighter_testnet)
    :return: WebSocket URL
    """
    base_ws_url = CONSTANTS.WS_URL if domain == "lighter" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None
) -> WebAssistantsFactory:
    """
    Build WebAssistantsFactory with Lighter-specific configuration.
    
    :param throttler: Rate limiter
    :param auth: Authentication handler
    :return: Configured WebAssistantsFactory
    """
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[LighterRESTPreProcessor()],
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
        rest_pre_processors=[LighterRESTPreProcessor()]
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    """Create rate limiter with Lighter's rate limits."""
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler: AsyncThrottler, domain: str) -> float:
    """
    Get current server time.
    
    For Lighter, we use local time as the API doesn't require strict time sync.
    
    :param throttler: Rate limiter
    :param domain: Domain identifier
    :return: Current timestamp
    """
    return time.time()


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    """
    Verify if a trading pair is enabled based on exchange information.
    
    :param rule: Exchange information for a trading pair
    :return: True if enabled, False otherwise
    """
    # Lighter doesn't have specific enable/disable flags in the API
    # All markets returned by the API are assumed to be tradeable
    return True


def order_type_to_lighter(order_type_str: str) -> int:
    """
    Convert Hummingbot order type to Lighter order type constant.
    
    :param order_type_str: Hummingbot order type string
    :return: Lighter order type integer
    """
    mapping = {
        "limit": CONSTANTS.ORDER_TYPE_LIMIT,
        "market": CONSTANTS.ORDER_TYPE_MARKET,
        "stop_loss": CONSTANTS.ORDER_TYPE_STOP_LOSS,
        "stop_loss_limit": CONSTANTS.ORDER_TYPE_STOP_LOSS_LIMIT,
        "take_profit": CONSTANTS.ORDER_TYPE_TAKE_PROFIT,
        "take_profit_limit": CONSTANTS.ORDER_TYPE_TAKE_PROFIT_LIMIT,
        "twap": CONSTANTS.ORDER_TYPE_TWAP,
    }
    return mapping.get(order_type_str.lower(), CONSTANTS.ORDER_TYPE_LIMIT)


def time_in_force_to_lighter(time_in_force_str: str) -> int:
    """
    Convert Hummingbot time in force to Lighter constant.
    
    :param time_in_force_str: Time in force string
    :return: Lighter time in force integer
    """
    mapping = {
        "ioc": CONSTANTS.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
        "immediate_or_cancel": CONSTANTS.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
        "gtt": CONSTANTS.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        "good_till_time": CONSTANTS.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        "gtc": CONSTANTS.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        "good_till_cancel": CONSTANTS.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        "post_only": CONSTANTS.ORDER_TIME_IN_FORCE_POST_ONLY,
        "alo": CONSTANTS.ORDER_TIME_IN_FORCE_POST_ONLY,
    }
    return mapping.get(time_in_force_str.lower(), CONSTANTS.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME)


def format_price_for_lighter(price: float, decimals: int = 8) -> int:
    """
    Format price as integer for Lighter API.
    
    Lighter expects prices and amounts as integers with specific decimal places.
    
    :param price: Price as float
    :param decimals: Number of decimal places
    :return: Price as integer
    """
    return int(price * (10 ** decimals))


def format_amount_for_lighter(amount: float, decimals: int = 8) -> int:
    """
    Format amount as integer for Lighter API.
    
    :param amount: Amount as float
    :param decimals: Number of decimal places
    :return: Amount as integer
    """
    return int(amount * (10 ** decimals))


def parse_price_from_lighter(price_int: int, decimals: int = 8) -> float:
    """
    Parse integer price from Lighter to float.
    
    :param price_int: Price as integer
    :param decimals: Number of decimal places
    :return: Price as float
    """
    return float(price_int) / (10 ** decimals)


def parse_amount_from_lighter(amount_int: int, decimals: int = 8) -> float:
    """
    Parse integer amount from Lighter to float.
    
    :param amount_int: Amount as integer
    :param decimals: Number of decimal places
    :return: Amount as float
    """
    return float(amount_int) / (10 ** decimals)

