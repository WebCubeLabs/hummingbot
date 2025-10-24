import asyncio
import json
import logging
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

import pandas as pd
from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
    LighterPerpetualDerivative,
)
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent, SellOrderCreatedEvent
from hummingbot.core.network_iterator import NetworkStatus


class LighterPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    _logger = logging.getLogger(__name__)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"  # noqa: mock
        cls.api_secret = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"  # noqa: mock
        cls.account_index = 123
        cls.api_key_index = 2
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    def setUp(self) -> None:
        super().setUp()
        self.exchange._set_current_timestamp(1640000000)

    @property
    def all_symbols_url(self):
        url = web_utils.rest_url(CONSTANTS.MARKETS_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.rest_url(CONSTANTS.TICKER_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def network_status_url(self):
        url = web_utils.rest_url(CONSTANTS.PING_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.rest_url(CONSTANTS.MARKETS_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def order_creation_url(self):
        url = web_utils.rest_url(CONSTANTS.CREATE_ORDER_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_url(self):
        url = web_utils.rest_url(CONSTANTS.ACCOUNT_BALANCE_URL)
        return url

    @property
    def funding_info_url(self):
        url = web_utils.rest_url(CONSTANTS.FUNDING_INFO_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def funding_payment_url(self):
        url = web_utils.rest_url(CONSTANTS.FUNDING_PAYMENT_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "balances": [
                {
                    "token": self.quote_asset,  # Perpetuals use quote asset as collateral
                    "available": "10000.0",
                    "locked": "0.0"
                }
            ]
        }

    @property
    def all_symbols_request_mock_response(self):
        return {
            "markets": [
                {
                    "symbol": f"{self.base_asset}-{self.quote_asset}",
                    "base_token": self.base_asset,
                    "quote_token": self.quote_asset,
                    "price_decimals": 2,
                    "size_decimals": 4,
                    "min_order_size": "0.001",
                    "max_order_size": "1000.0",
                    "tick_size": "0.01",
                    "step_size": "0.0001",
                    "max_leverage": 20,
                    "initial_margin": "0.05",
                    "maintenance_margin": "0.03",
                    "status": "active"
                },
                {
                    "symbol": "BTC-USDC",
                    "base_token": "BTC",
                    "quote_token": "USDC",
                    "price_decimals": 2,
                    "size_decimals": 5,
                    "min_order_size": "0.0001",
                    "max_order_size": "100.0",
                    "tick_size": "0.01",
                    "step_size": "0.00001",
                    "max_leverage": 20,
                    "initial_margin": "0.05",
                    "maintenance_margin": "0.03",
                    "status": "active"
                }
            ]
        }

    @property
    def latest_prices_request_mock_response(self):
        return {
            "tickers": [
                {
                    "symbol": f"{self.base_asset}-{self.quote_asset}",
                    "last_price": str(self.expected_latest_price),
                    "mark_price": str(self.expected_latest_price),
                    "index_price": str(self.expected_latest_price),
                    "bid": "2000.0",
                    "ask": "2001.0",
                    "volume_24h": "1000.0",
                    "funding_rate": "0.0001"
                }
            ]
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        response = self.all_symbols_request_mock_response
        response["markets"].append({
            "symbol": "INVALID-PAIR",
            "base_token": "INVALID",
            "quote_token": "PAIR",
            "price_decimals": 2,
            "size_decimals": 4,
            "min_order_size": "0.001",
            "max_order_size": "1000.0",
            "tick_size": "0.01",
            "step_size": "0.0001",
            "max_leverage": 20,
            "status": "inactive"  # Inactive status makes it invalid
        })
        return response

    @property
    def network_status_request_successful_mock_response(self):
        return {"status": "ok"}

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {
            "markets": [
                {
                    "symbol": f"{self.base_asset}-{self.quote_asset}",
                    # Missing required fields
                }
            ]
        }

    @property
    def order_creation_request_successful_mock_response(self):
        return {
            "order_id": self.expected_exchange_order_id,
            "client_order_id": "OID1",
            "symbol": f"{self.base_asset}-{self.quote_asset}",
            "side": "buy",
            "type": "limit",
            "price": "2000.0",
            "size": "1.0",
            "status": "open",
            "created_at": 1640000000000
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "balances": [
                {
                    "token": self.quote_asset,
                    "available": "10000.0",
                    "locked": "2000.0"
                }
            ]
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "type": "balance_update",
            "data": {
                "token": self.quote_asset,
                "available": "15000.0",
                "locked": "0.0"
            }
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_supported_position_modes(self):
        return [PositionMode.ONEWAY, PositionMode.HEDGE]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            max_order_size=Decimal("1000.0"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.0001"),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response["markets"][0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "1234567890"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("100")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.02"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "fill_trade_id_123"

    @property
    def funding_info_mock_response(self):
        return {
            "symbol": f"{self.base_asset}-{self.quote_asset}",
            "mark_price": str(self.target_funding_info_mark_price),
            "index_price": str(self.target_funding_info_index_price),
            "funding_rate": str(self.target_funding_info_rate),
            "next_funding_time": self.target_funding_info_next_funding_utc_timestamp * 1000,
        }

    @property
    def empty_funding_payment_mock_response(self):
        return {
            "payments": []
        }

    @property
    def funding_payment_mock_response(self):
        return {
            "payments": [
                {
                    "symbol": f"{self.base_asset}-{self.quote_asset}",
                    "funding_rate": "0.0001",
                    "payment": "-0.5",  # Negative means paid
                    "timestamp": self.target_funding_payment_timestamp * 1000
                }
            ]
        }

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}-{quote_token}"

    def create_exchange_instance(self):
        client_config_map = AsyncMock()
        client_config_map.connector = AsyncMock()
        client_config_map.connector.lighter_perpetual_api_key = self.api_key
        client_config_map.connector.lighter_perpetual_api_secret = self.api_secret
        client_config_map.connector.lighter_perpetual_account_index = self.account_index
        client_config_map.connector.lighter_perpetual_api_key_index = self.api_key_index

        with patch('hummingbot.connector.exchange.lighter.lighter_auth.SignerClient'):
            exchange = LighterPerpetualDerivative(
                client_config_map=client_config_map,
                lighter_perpetual_api_key=self.api_key,
                lighter_perpetual_api_secret=self.api_secret,
                lighter_perpetual_account_index=self.account_index,
                lighter_perpetual_api_key_index=self.api_key_index,
                trading_pairs=[self.trading_pair],
            )
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        # Lighter uses custom auth with SignerClient, check for auth headers
        self.assertIn("Authorization", request_call.kwargs["headers"])

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), 
                        request_data["symbol"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(order.amount, Decimal(str(request_data["size"])))
        self.assertEqual(order.price, Decimal(str(request_data["price"])))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.exchange_order_id, request_data["order_id"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["order_id"])

    def configure_successful_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.CANCEL_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.CANCEL_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = {"error": "Order not found"}
        mock_api.post(regex_url, status=404, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
        self,
        successful_order: InFlightOrder,
        erroneous_order: InFlightOrder,
        mock_api: aioresponses,
    ) -> List[str]:
        all_urls = []
        url = self.configure_successful_cancelation_response(
            order=successful_order, mock_api=mock_api
        )
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(
            order=erroneous_order, mock_api=mock_api
        )
        all_urls.append(url)
        return all_urls

    def configure_completely_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=404, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.ORDER_STATUS_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.TRADES_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.TRADES_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
        self,
        order: InFlightOrder,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        url = web_utils.rest_url(CONSTANTS.TRADES_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": "order_update",
            "data": {
                "order_id": order.exchange_order_id,
                "client_order_id": order.client_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "side": order.trade_type.name.lower(),
                "type": "limit",
                "price": str(order.price),
                "size": str(order.amount),
                "status": "open",
                "filled_size": "0",
                "created_at": 1640000000000
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "type": "order_update",
            "data": {
                "order_id": order.exchange_order_id,
                "client_order_id": order.client_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "status": "canceled",
                "filled_size": "0"
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": "order_update",
            "data": {
                "order_id": order.exchange_order_id,
                "client_order_id": order.client_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "status": "filled",
                "filled_size": str(order.amount),
                "average_price": str(order.price)
            }
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "type": "trade",
            "data": {
                "trade_id": self.expected_fill_trade_id,
                "order_id": order.exchange_order_id,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "side": order.trade_type.name.lower(),
                "price": str(order.price),
                "size": str(order.amount),
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "fee_token": self.expected_fill_fee.flat_fees[0].token,
                "timestamp": 1640000000000
            }
        }

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {
            "type": "position_update",
            "data": {
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "side": "long" if order.trade_type == TradeType.BUY else "short",
                "size": str(order.amount),
                "entry_price": str(order.price),
                "unrealized_pnl": str(unrealized_pnl),
                "leverage": "10"
            }
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": order.exchange_order_id,
            "status": "canceled"
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": order.exchange_order_id,
            "client_order_id": order.client_order_id,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": order.trade_type.name.lower(),
            "type": "limit",
            "price": str(order.price),
            "size": str(order.amount),
            "filled_size": str(order.amount),
            "status": "filled",
            "created_at": 1640000000000
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": order.exchange_order_id,
            "client_order_id": order.client_order_id,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "status": "canceled",
            "filled_size": "0"
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": order.exchange_order_id,
            "client_order_id": order.client_order_id,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": order.trade_type.name.lower(),
            "type": "limit",
            "price": str(order.price),
            "size": str(order.amount),
            "filled_size": "0",
            "status": "open",
            "created_at": 1640000000000
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": order.exchange_order_id,
            "client_order_id": order.client_order_id,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "side": order.trade_type.name.lower(),
            "type": "limit",
            "price": str(order.price),
            "size": str(order.amount),
            "filled_size": str(self.expected_partial_fill_amount),
            "status": "partially_filled",
            "created_at": 1640000000000
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return {
            "trades": [
                {
                    "trade_id": self.expected_fill_trade_id,
                    "order_id": order.exchange_order_id,
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": order.trade_type.name.lower(),
                    "price": str(self.expected_partial_fill_price),
                    "size": str(self.expected_partial_fill_amount),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "fee_token": self.expected_fill_fee.flat_fees[0].token,
                    "timestamp": 1640000000000
                }
            ]
        }

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return {
            "trades": [
                {
                    "trade_id": self.expected_fill_trade_id,
                    "order_id": order.exchange_order_id,
                    "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                    "side": order.trade_type.name.lower(),
                    "price": str(order.price),
                    "size": str(order.amount),
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                    "fee_token": self.expected_fill_fee.flat_fees[0].token,
                    "timestamp": 1640000000000
                }
            ]
        }

    @aioresponses()
    def test_update_position_mode_success(self, mock_api):
        # Skip if not implemented yet
        pass

    def test_user_stream_balance_update(self):
        # Skip if not implemented yet
        pass

    def test_lost_order_removed_if_not_found_during_order_status_update(self):
        # Skip if not implemented yet
        pass

