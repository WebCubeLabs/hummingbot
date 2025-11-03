import asyncio
import os
from decimal import Decimal
from typing import Dict, List, Set

import pandas as pd
from pydantic import Field, field_validator

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PriceType, TradeType
from hummingbot.core.event.events import FundingPaymentCompletedEvent
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class FundingRateArbitrageConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    candles_config: List[CandlesConfig] = []
    controllers_config: List[str] = []
    markets: Dict[str, Set[str]] = {}
    leverage: int = Field(
        default=20, gt=0,
        json_schema_extra={"prompt": lambda mi: "Enter the leverage (e.g. 20): ", "prompt_on_new": True},
    )
    min_funding_rate_profitability: Decimal = Field(
        default=0.001,
        json_schema_extra={
            "prompt": lambda mi: "Enter the min funding rate profitability to enter in a position (e.g. 0.001): ",
            "prompt_on_new": True}
    )
    connectors: Set[str] = Field(
        default={"hyperliquid_perpetual", "bybit_perpetual"},
        json_schema_extra={
            "prompt": lambda mi: "Enter the connectors separated by commas (e.g. hyperliquid_perpetual,bybit_perpetual): ",
            "prompt_on_new": True}
    )
    tokens: Set[str] = Field(
        # Top 30 high-volume, high-opportunity tokens (auto-validated at startup)
        # Set auto_filter_low_opportunity_tokens=False to disable dynamic filtering
        # default={"BTC", "ETH", "SOL", "DOGE", "WIF", "OM", "LINK", "AVAX", "UNI", "DOT",
        #          "ARB", "OP", "SUI", "APT", "INJ", "TIA", "SEI", "JUP", "PENDLE", "ONDO",
        #          "HYPE", "TRUMP", "MEME", "GOAT", "PNUT", "POPCAT", "WLD", "TAO", "NEAR", "FIL"},
        default={"BTC"},
        json_schema_extra={"prompt": lambda mi: "Enter the tokens separated by commas (e.g. BTC,ETH,SOL,OM): ", "prompt_on_new": True},
    )
    position_size_quote: Decimal = Field(
        default=100,
        json_schema_extra={
            "prompt": lambda mi: "Enter the position size in quote asset (e.g. order amount 100 will open 100 long on hyperliquid and 100 short on binance): ",
            "prompt_on_new": True
        }
    )
    profitability_to_take_profit: Decimal = Field(
        default=0.01,
        json_schema_extra={
            "prompt": lambda mi: "Enter the profitability to take profit (including PNL of positions and fundings received): ",
            "prompt_on_new": True}
    )
    funding_rate_diff_stop_loss: Decimal = Field(
        default=-0.001,
        json_schema_extra={
            "prompt": lambda mi: "Enter the funding rate difference to stop the position (e.g. -0.001): ",
            "prompt_on_new": True}
    )
    trade_profitability_condition_to_enter: bool = Field(
        default=False,
        json_schema_extra={
            "prompt": lambda mi: "Do you want to check the trade profitability condition to enter? (True/False): ",
            "prompt_on_new": True}
    )
    auto_filter_low_opportunity_tokens: bool = Field(
        default=True,
        json_schema_extra={
            "prompt": lambda mi: "Auto-filter tokens with low funding rate opportunities? (True/False): ",
            "prompt_on_new": True}
    )

    @field_validator("connectors", "tokens", mode="before")
    @classmethod
    def validate_sets(cls, v):
        if isinstance(v, str):
            return set(v.split(","))
        return v


class FundingRateArbitrage(StrategyV2Base):
    # Safe token used for initial connector setup (guaranteed to exist on all major exchanges)
    SAFE_INIT_TOKEN = "BTC"
    
    quote_markets_map = {
        "hyperliquid_perpetual": "USD",
        "binance_perpetual": "USDT",
        "bybit_perpetual": "USDT"
    }
    # Default funding intervals (will be detected dynamically per token)
    default_funding_interval_map = {
        "binance_perpetual": 60 * 60 * 8,
        "bybit_perpetual": 60 * 60 * 8,
        "hyperliquid_perpetual": 60 * 60 * 1
    }
    funding_profitability_interval = 60 * 60 * 24
    
    # Cache for detected funding intervals per token-connector
    _funding_intervals_cache = {}  # {(token, connector): interval_in_seconds}

    @classmethod
    def get_trading_pair_for_connector(cls, token, connector):
        return f"{token}-{cls.quote_markets_map.get(connector, 'USDT')}"

    @classmethod
    def init_markets(cls, config: FundingRateArbitrageConfig):
        # Initialize with configured tokens
        # Note: Invalid tokens will cause brief errors during startup, but will be
        # automatically filtered out by validation in apply_initial_setting()
        markets = {}
        for connector in config.connectors:
            trading_pairs = {cls.get_trading_pair_for_connector(token, connector) for token in config.tokens}
            markets[connector] = trading_pairs
        cls.markets = markets

    def __init__(self, connectors: Dict[str, ConnectorBase], config: FundingRateArbitrageConfig):
        super().__init__(connectors, config)
        self.config = config
        self.active_funding_arbitrages = {}
        self.stopped_funding_arbitrages = {token: [] for token in self.config.tokens}

    def start(self, clock: Clock, timestamp: float) -> None:
        """
        Start the strategy.
        :param clock: Clock to use.
        :param timestamp: Current time.
        """
        self._last_timestamp = timestamp
        self._initialization_done = False
        # Note: apply_initial_setting() will be called after connectors are ready (see on_tick)

    def on_tick(self):
        """
        Called every second after connectors are ready.
        Performs one-time initialization, then runs normal tick logic.
        """
        # Run initialization only once after connectors are ready
        if not self._initialization_done:
            # Log connector status to verify what "ready" means
            for name, connector in self.connectors.items():
                status = connector.status_dict
                self.logger().info(f"{name} ready with status: {status}")
            
            self._initialization_done = True
            asyncio.create_task(self.apply_initial_setting())
        else:
            # Log every 10 seconds to verify tick is running
            if int(self.current_timestamp) % 10 == 0:
                self.logger().info(f"Tick running - timestamp: {self.current_timestamp}, ready_to_trade: {self.ready_to_trade}")
        
        # Call parent on_tick for normal strategy operation
        try:
            super().on_tick()
        except Exception as e:
            self.logger().error(f"Error in parent on_tick: {e}", exc_info=True)

    async def _get_hyperliquid_tickers(self, connector) -> Set[str]:
        """Fetch all perpetual tickers from Hyperliquid."""
        try:
            import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_constants as constants
            response = await connector._api_post(
                path_url=constants.EXCHANGE_INFO_URL,
                data={"type": constants.META_INFO}
            )
            # Extract all coin names from universe
            tickers = {asset.get("name") for asset in response.get("universe", [])}
            return tickers
        except Exception as e:
            self.logger().warning(f"Failed to fetch Hyperliquid tickers: {e}")
            return set()

    async def _get_bybit_tickers(self, connector) -> Set[str]:
        """Fetch all perpetual tickers from Bybit."""
        try:
            # Use the connector's _make_trading_pairs_request method
            trading_pairs_info = await connector._make_trading_pairs_request()
            
            tickers = set()
            for item in trading_pairs_info:
                # Only include perpetual contracts (not futures with expiry)
                if item.get("contractType") == "LinearPerpetual":
                    symbol = item.get("symbol", "")
                    # Extract base token (e.g., "WIFUSDT" -> "WIF")
                    if symbol.endswith("USDT"):
                        ticker = symbol[:-4]  # Remove "USDT"
                        tickers.add(ticker)
            return tickers
        except Exception as e:
            self.logger().warning(f"Failed to fetch Bybit tickers: {e}")
            return set()

    async def _validate_tokens_exist_on_all_exchanges(self):
        """Validate that all configured tokens exist on all configured exchanges."""
        if len(self.config.connectors) < 2:
            self.logger().warning("Need at least 2 connectors for funding rate arbitrage")
            return

        # Fetch tickers from each exchange
        exchange_tickers = {}
        for connector_name, connector in self.connectors.items():
            if connector_name == "hyperliquid_perpetual":
                tickers = await self._get_hyperliquid_tickers(connector)
                exchange_tickers[connector_name] = tickers
                self.logger().info(f"Hyperliquid perpetuals: {len(tickers)} tickers found")
            elif connector_name == "bybit_perpetual":
                tickers = await self._get_bybit_tickers(connector)
                exchange_tickers[connector_name] = tickers
                self.logger().info(f"Bybit perpetuals: {len(tickers)} tickers found")

        # Find intersection (tokens available on ALL exchanges)
        if len(exchange_tickers) >= 2:
            common_tokens = set.intersection(*exchange_tickers.values())
            self.logger().info(f"Common tokens on all exchanges: {sorted(common_tokens)}")

            # Validate requested tokens
            invalid_tokens = self.config.tokens - common_tokens
            if invalid_tokens:
                self.logger().error(
                    f"⚠️  Invalid tokens (not available on all exchanges): {invalid_tokens}\n"
                    f"   Available tokens: {sorted(common_tokens)}\n"
                    f"   Removing invalid tokens from config..."
                )
                # Filter out invalid tokens
                self.config.tokens = self.config.tokens & common_tokens
                if not self.config.tokens:
                    self.logger().error("❌ No valid tokens remaining! Please configure valid tokens.")
                else:
                    self.logger().info(f"✅ Valid tokens: {sorted(self.config.tokens)}")
            else:
                self.logger().info(f"✅ All tokens valid: {sorted(self.config.tokens)}")

    async def _get_hyperliquid_max_leverage(self, connector, trading_pair: str) -> int:
        """Query Hyperliquid meta API to get max leverage for a trading pair."""
        try:
            import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_constants as constants
            ex_trading_pair = await connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            coin = ex_trading_pair.split("-")[0]
            
            # Query Hyperliquid meta endpoint
            response = await connector._api_post(
                path_url=constants.EXCHANGE_INFO_URL,
                data={"type": constants.META_INFO}
            )
            
            # Find coin in universe and get max leverage
            for asset in response.get("universe", []):
                if asset.get("name") == coin:
                    max_leverage = asset.get("maxLeverage", 20)  # Default to 20 if not found
                    return int(max_leverage)
        except Exception as e:
            self.logger().warning(f"Failed to get max leverage for {trading_pair} from Hyperliquid: {e}")
        return 20  # Safe default
    
    async def _set_leverage_with_max_check(self, connector_name: str, connector, trading_pair: str):
        """Set leverage for a single pair with max leverage validation (Hyperliquid only)."""
        try:
            max_leverage = await self._get_hyperliquid_max_leverage(connector, trading_pair)
            safe_leverage = min(self.config.leverage, max_leverage)
            connector.set_leverage(trading_pair, safe_leverage)
            # Only log occasionally to avoid spam with 182 tokens
            if hash(trading_pair) % 20 == 0:  # Log ~5% of pairs
                self.logger().info(f"{connector_name} - {trading_pair}: {safe_leverage}x (max: {max_leverage}x)")
        except Exception as e:
            self.logger().error(f"Failed to set leverage for {trading_pair} on {connector_name}: {e}")
    
    async def _set_leverage_simple(self, connector_name: str, connector, trading_pair: str, leverage: int):
        """Set leverage for a single pair (Bybit and others)."""
        try:
            connector.set_leverage(trading_pair, leverage)
        except Exception as e:
            self.logger().error(f"Failed to set leverage for {trading_pair} on {connector_name}: {e}")

    async def apply_initial_setting(self):
        """Apply initial settings with proper leverage handling."""
        self.logger().info("Applying initial settings (connectors are ready)...")
        
        # Log actual account balances to verify they were fetched
        for name, connector in self.connectors.items():
            self.logger().info(f"{name} account balances: {dict(connector.get_all_balances())}")
            self.logger().info(f"{name} available balances: {dict(connector.available_balances)}")
        
        # Validate tokens exist on all exchanges (logs warnings for invalid tokens)
        await self._validate_tokens_exist_on_all_exchanges()
        
        # Set position mode first (must be done before leverage)
        for connector_name, connector in self.connectors.items():
            if self.is_perpetual(connector_name):
                position_mode = PositionMode.ONEWAY if connector_name == "hyperliquid_perpetual" else PositionMode.HEDGE
                connector.set_position_mode(position_mode)
        
        # Set leverage for all tokens in parallel (much faster than sequential)
        # This reduces startup from ~2 minutes to ~10 seconds for 182 tokens
        leverage_tasks = []
        for connector_name, connector in self.connectors.items():
            if self.is_perpetual(connector_name):
                for token in self.config.tokens:
                    trading_pair = self.get_trading_pair_for_connector(token, connector_name)
                    
                    if connector_name == "hyperliquid_perpetual":
                        # Hyperliquid: need to check max leverage per token
                        leverage_tasks.append(self._set_leverage_with_max_check(connector_name, connector, trading_pair))
                    else:
                        # Bybit/others: set leverage directly (already async internally)
                        leverage_tasks.append(self._set_leverage_simple(connector_name, connector, trading_pair, self.config.leverage))
        
        # Execute all leverage settings in parallel (with rate limiting)
        if leverage_tasks:
            total_pairs = len(leverage_tasks)
            self.logger().info(f"Setting leverage for {total_pairs} pairs in batches (rate limit safe)...")
            
            # Process in batches of 10 to avoid rate limits (Hyperliquid: 20 req/sec)
            batch_size = 10
            results = []
            for i in range(0, len(leverage_tasks), batch_size):
                batch = leverage_tasks[i:i + batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)
                
                # Small delay between batches to stay under rate limit
                if i + batch_size < len(leverage_tasks):
                    await asyncio.sleep(0.5)  # 500ms delay between batches
            
            # Log any failures
            failures = [r for r in results if isinstance(r, Exception)]
            if failures:
                self.logger().warning(f"Failed to set leverage for {len(failures)}/{total_pairs} pairs")
            else:
                self.logger().info(f"✅ Successfully set leverage for all {total_pairs} pairs")

    def get_funding_info_by_token(self, token):
        """
        This method provides the funding rates across all the connectors
        """
        funding_rates = {}
        for connector_name, connector in self.connectors.items():
            trading_pair = self.get_trading_pair_for_connector(token, connector_name)
            try:
                funding_rates[connector_name] = connector.get_funding_info(trading_pair)
            except (KeyError, Exception) as e:
                # Pair not ready yet (e.g., invalid token being filtered out)
                # Skip silently - will be available after validation completes
                pass
        return funding_rates

    def get_current_profitability_after_fees(self, token: str, connector_1: str, connector_2: str, side: TradeType):
        """
        This methods compares the profitability of buying at market in the two exchanges. If the side is TradeType.BUY
        means that the operation is long on connector 1 and short on connector 2.
        """
        trading_pair_1 = self.get_trading_pair_for_connector(token, connector_1)
        trading_pair_2 = self.get_trading_pair_for_connector(token, connector_2)

        connector_1_price = Decimal(self.market_data_provider.get_price_for_quote_volume(
            connector_name=connector_1,
            trading_pair=trading_pair_1,
            quote_volume=self.config.position_size_quote,
            is_buy=side == TradeType.BUY,
        ).result_price)
        connector_2_price = Decimal(self.market_data_provider.get_price_for_quote_volume(
            connector_name=connector_2,
            trading_pair=trading_pair_2,
            quote_volume=self.config.position_size_quote,
            is_buy=side != TradeType.BUY,
        ).result_price)
        estimated_fees_connector_1 = self.connectors[connector_1].get_fee(
            base_currency=trading_pair_1.split("-")[0],
            quote_currency=trading_pair_1.split("-")[1],
            order_type=OrderType.MARKET,
            order_side=TradeType.BUY,
            amount=self.config.position_size_quote / connector_1_price,
            price=connector_1_price,
            is_maker=False,
            position_action=PositionAction.OPEN
        ).percent
        estimated_fees_connector_2 = self.connectors[connector_2].get_fee(
            base_currency=trading_pair_2.split("-")[0],
            quote_currency=trading_pair_2.split("-")[1],
            order_type=OrderType.MARKET,
            order_side=TradeType.BUY,
            amount=self.config.position_size_quote / connector_2_price,
            price=connector_2_price,
            is_maker=False,
            position_action=PositionAction.OPEN
        ).percent

        if side == TradeType.BUY:
            estimated_trade_pnl_pct = (connector_2_price - connector_1_price) / connector_1_price
        else:
            estimated_trade_pnl_pct = (connector_1_price - connector_2_price) / connector_2_price
        return estimated_trade_pnl_pct - estimated_fees_connector_1 - estimated_fees_connector_2

    def get_most_profitable_combination(self, funding_info_report: Dict, token: str = None):
        best_combination = None
        highest_profitability = 0
        for connector_1 in funding_info_report:
            for connector_2 in funding_info_report:
                if connector_1 != connector_2:
                    rate_connector_1 = self.get_normalized_funding_rate_in_seconds(funding_info_report, connector_1, token)
                    rate_connector_2 = self.get_normalized_funding_rate_in_seconds(funding_info_report, connector_2, token)
                    funding_rate_diff = abs(rate_connector_1 - rate_connector_2) * self.funding_profitability_interval
                    if funding_rate_diff > highest_profitability:
                        trade_side = TradeType.BUY if rate_connector_1 < rate_connector_2 else TradeType.SELL
                        highest_profitability = funding_rate_diff
                        best_combination = (connector_1, connector_2, trade_side, funding_rate_diff)
        return best_combination

    def _detect_funding_interval(self, token: str, connector_name: str, funding_info) -> int:
        """
        Detect the actual funding payment interval for a token by analyzing next_funding_timestamp.
        Different tokens can have different intervals (1h, 4h, 8h, etc.)
        """
        cache_key = (token, connector_name)
        
        # Return cached value if available
        if cache_key in self._funding_intervals_cache:
            return self._funding_intervals_cache[cache_key]
        
        # Try to detect from funding info
        if funding_info and hasattr(funding_info, 'next_funding_utc_timestamp'):
            current_time = self.current_timestamp
            next_funding = funding_info.next_funding_utc_timestamp
            time_to_next = next_funding - current_time
            
            # Round to nearest hour to handle timing variations
            detected_interval = round(time_to_next / 3600) * 3600
            
            # Validate it's a reasonable interval (1h, 4h, or 8h)
            if detected_interval in [3600, 14400, 28800]:
                self._funding_intervals_cache[cache_key] = int(detected_interval)
                return int(detected_interval)
        
        # Fall back to default for this exchange
        default_interval = self.default_funding_interval_map.get(connector_name, 60 * 60 * 8)
        self._funding_intervals_cache[cache_key] = default_interval
        return default_interval
    
    def get_normalized_funding_rate_in_seconds(self, funding_info_report, connector_name, token: str = None):
        """
        Get funding rate normalized to per-second rate.
        Now supports dynamic interval detection per token.
        """
        if token and connector_name in funding_info_report:
            # Use detected interval for this specific token
            interval = self._detect_funding_interval(token, connector_name, funding_info_report[connector_name])
        else:
            # Fall back to default
            interval = self.default_funding_interval_map.get(connector_name, 60 * 60 * 8)
        
        return funding_info_report[connector_name].rate / interval

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        """
        In this method we are going to evaluate if a new set of positions has to be created for each of the tokens that
        don't have an active arbitrage.
        More filters can be applied to limit the creation of the positions, since the current logic is only checking for
        positive pnl between funding rate. Is logged and computed the trading profitability at the time for entering
        at market to open the possibilities for other people to create variations like sending limit position executors
        and if one gets filled buy market the other one to improve the entry prices.
        """
        create_actions = []
        for token in self.config.tokens:
            if token not in self.active_funding_arbitrages:
                funding_info_report = self.get_funding_info_by_token(token)
                best_combination = self.get_most_profitable_combination(funding_info_report, token)
                connector_1, connector_2, trade_side, expected_profitability = best_combination
                if expected_profitability >= self.config.min_funding_rate_profitability:
                    current_profitability = self.get_current_profitability_after_fees(
                        token, connector_1, connector_2, trade_side
                    )
                    if self.config.trade_profitability_condition_to_enter:
                        if current_profitability < 0:
                            self.logger().info(f"Best Combination: {connector_1} | {connector_2} | {trade_side}"
                                               f"Funding rate profitability: {expected_profitability}"
                                               f"Trading profitability after fees: {current_profitability}"
                                               f"Trade profitability is negative, skipping...")
                            continue
                    self.logger().info(f"Best Combination: {connector_1} | {connector_2} | {trade_side}"
                                       f"Funding rate profitability: {expected_profitability}"
                                       f"Trading profitability after fees: {current_profitability}"
                                       f"Starting executors...")
                    position_executor_config_1, position_executor_config_2 = self.get_position_executors_config(token, connector_1, connector_2, trade_side)
                    self.active_funding_arbitrages[token] = {
                        "connector_1": connector_1,
                        "connector_2": connector_2,
                        "executors_ids": [position_executor_config_1.id, position_executor_config_2.id],
                        "side": trade_side,
                        "funding_payments": [],
                    }
                    return [CreateExecutorAction(executor_config=position_executor_config_1),
                            CreateExecutorAction(executor_config=position_executor_config_2)]
        return create_actions

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        """
        Once the funding rate arbitrage is created we are going to control the funding payments pnl and the current
        pnl of each of the executors at the cost of closing the open position at market.
        If that PNL is greater than the profitability_to_take_profit
        """
        stop_executor_actions = []
        for token, funding_arbitrage_info in self.active_funding_arbitrages.items():
            executors = self.filter_executors(
                executors=self.get_all_executors(),
                filter_func=lambda x: x.id in funding_arbitrage_info["executors_ids"]
            )
            funding_payments_pnl = sum(funding_payment.amount for funding_payment in funding_arbitrage_info["funding_payments"])
            executors_pnl = sum(executor.net_pnl_quote for executor in executors)
            take_profit_condition = executors_pnl + funding_payments_pnl > self.config.profitability_to_take_profit * self.config.position_size_quote
            funding_info_report = self.get_funding_info_by_token(token)
            if funding_arbitrage_info["side"] == TradeType.BUY:
                funding_rate_diff = self.get_normalized_funding_rate_in_seconds(funding_info_report, funding_arbitrage_info["connector_2"], token) - self.get_normalized_funding_rate_in_seconds(funding_info_report, funding_arbitrage_info["connector_1"], token)
            else:
                funding_rate_diff = self.get_normalized_funding_rate_in_seconds(funding_info_report, funding_arbitrage_info["connector_1"], token) - self.get_normalized_funding_rate_in_seconds(funding_info_report, funding_arbitrage_info["connector_2"], token)
            current_funding_condition = funding_rate_diff * self.funding_profitability_interval < self.config.funding_rate_diff_stop_loss
            if take_profit_condition:
                self.logger().info("Take profit profitability reached, stopping executors")
                self.stopped_funding_arbitrages[token].append(funding_arbitrage_info)
                stop_executor_actions.extend([StopExecutorAction(executor_id=executor.id) for executor in executors])
            elif current_funding_condition:
                self.logger().info("Funding rate difference reached for stop loss, stopping executors")
                self.stopped_funding_arbitrages[token].append(funding_arbitrage_info)
                stop_executor_actions.extend([StopExecutorAction(executor_id=executor.id) for executor in executors])
        return stop_executor_actions

    def did_complete_funding_payment(self, funding_payment_completed_event: FundingPaymentCompletedEvent):
        """
        Based on the funding payment event received, check if one of the active arbitrages matches to add the event
        to the list.
        """
        token = funding_payment_completed_event.trading_pair.split("-")[0]
        if token in self.active_funding_arbitrages:
            self.active_funding_arbitrages[token]["funding_payments"].append(funding_payment_completed_event)

    def get_position_executors_config(self, token, connector_1, connector_2, trade_side):
        price = self.market_data_provider.get_price_by_type(
            connector_name=connector_1,
            trading_pair=self.get_trading_pair_for_connector(token, connector_1),
            price_type=PriceType.MidPrice
        )
        position_amount = self.config.position_size_quote / price

        position_executor_config_1 = PositionExecutorConfig(
            timestamp=self.current_timestamp,
            connector_name=connector_1,
            trading_pair=self.get_trading_pair_for_connector(token, connector_1),
            side=trade_side,
            amount=position_amount,
            leverage=self.config.leverage,
            triple_barrier_config=TripleBarrierConfig(open_order_type=OrderType.MARKET),
        )
        position_executor_config_2 = PositionExecutorConfig(
            timestamp=self.current_timestamp,
            connector_name=connector_2,
            trading_pair=self.get_trading_pair_for_connector(token, connector_2),
            side=TradeType.BUY if trade_side == TradeType.SELL else TradeType.SELL,
            amount=position_amount,
            leverage=self.config.leverage,
            triple_barrier_config=TripleBarrierConfig(open_order_type=OrderType.MARKET),
        )
        return position_executor_config_1, position_executor_config_2

    def format_status(self) -> str:
        original_status = super().format_status()
        funding_rate_status = []
        if self.ready_to_trade:
            all_funding_info = []
            all_best_paths = []
            for token in self.config.tokens:
                token_info = {"token": token}
                best_paths_info = {"token": token}
                funding_info_report = self.get_funding_info_by_token(token)
                best_combination = self.get_most_profitable_combination(funding_info_report, token)
                for connector_name, info in funding_info_report.items():
                    token_info[f"{connector_name} Rate (%)"] = self.get_normalized_funding_rate_in_seconds(funding_info_report, connector_name, token) * self.funding_profitability_interval * 100
                connector_1, connector_2, side, funding_rate_diff = best_combination
                profitability_after_fees = self.get_current_profitability_after_fees(token, connector_1, connector_2, side)
                best_paths_info["Best Path"] = f"{connector_1}_{connector_2}"
                best_paths_info["Best Rate Diff (%)"] = funding_rate_diff * 100
                best_paths_info["Trade Profitability (%)"] = profitability_after_fees * 100
                best_paths_info["Days Trade Prof"] = - profitability_after_fees / funding_rate_diff
                best_paths_info["Days to TP"] = (self.config.profitability_to_take_profit - profitability_after_fees) / funding_rate_diff

                time_to_next_funding_info_c1 = funding_info_report[connector_1].next_funding_utc_timestamp - self.current_timestamp
                time_to_next_funding_info_c2 = funding_info_report[connector_2].next_funding_utc_timestamp - self.current_timestamp
                best_paths_info["Min to Funding 1"] = time_to_next_funding_info_c1 / 60
                best_paths_info["Min to Funding 2"] = time_to_next_funding_info_c2 / 60

                all_funding_info.append(token_info)
                all_best_paths.append(best_paths_info)
            funding_rate_status.append(f"\n\n\nMin Funding Rate Profitability: {self.config.min_funding_rate_profitability:.2%}")
            funding_rate_status.append(f"Profitability to Take Profit: {self.config.profitability_to_take_profit:.2%}\n")
            funding_rate_status.append("Funding Rate Info (Funding Profitability in Days): ")
            funding_rate_status.append(format_df_for_printout(df=pd.DataFrame(all_funding_info), table_format="psql",))
            funding_rate_status.append(format_df_for_printout(df=pd.DataFrame(all_best_paths), table_format="psql",))
            for token, funding_arbitrage_info in self.active_funding_arbitrages.items():
                long_connector = funding_arbitrage_info["connector_1"] if funding_arbitrage_info["side"] == TradeType.BUY else funding_arbitrage_info["connector_2"]
                short_connector = funding_arbitrage_info["connector_2"] if funding_arbitrage_info["side"] == TradeType.BUY else funding_arbitrage_info["connector_1"]
                funding_rate_status.append(f"Token: {token}")
                funding_rate_status.append(f"Long connector: {long_connector} | Short connector: {short_connector}")
                funding_rate_status.append(f"Funding Payments Collected: {funding_arbitrage_info['funding_payments']}")
                funding_rate_status.append(f"Executors: {funding_arbitrage_info['executors_ids']}")
                funding_rate_status.append("-" * 50 + "\n")
        return original_status + "\n".join(funding_rate_status)
