#!/usr/bin/env python
"""
Hummingbot Freqtrading-Style Starter
=====================================

This script runs Hummingbot in a simplified, single-strategy mode similar to Freqtrading.
It's designed to run one strategy per Docker container with easy configuration.

Usage:
    python hummingbot_run.py --strategy <strategy_name> --config <config_file> [--password <password>]

Environment Variables:
    STRATEGY_NAME:      Name of strategy script (without .py extension)
    STRATEGY_CONFIG:    YAML config file name (e.g., my_strategy_config.yml)
    CONFIG_PASSWORD:    Password for encrypted config (default: empty string)
    HEADLESS_MODE:      true/false (default: true)
    LOG_LEVEL:          DEBUG, INFO, WARNING, ERROR (default: INFO)

Examples:
    # Run with environment variables (Docker)
    export STRATEGY_NAME=v2_funding_rate_arb
    export STRATEGY_CONFIG=funding_config.yml
    export CONFIG_PASSWORD=mypassword
    python hummingbot_run.py

    # Run with command-line arguments
    python hummingbot_run.py --strategy simple_pmm --config pmm_config.yml --password admin

    # Run headless on container
    docker run -e STRATEGY_NAME=v2_funding_rate_arb -e STRATEGY_CONFIG=config.yml hummingbot/hummingbot
"""

import argparse
import asyncio
import importlib
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add bin directory to path
sys.path.insert(0, str(Path(__file__).parent))
import path_util  # noqa: F401

from bin.hummingbot import detect_available_port
from hummingbot import init_logging
from hummingbot.client.command.start_command import GATEWAY_READY_TIMEOUT
from hummingbot.client.config.config_crypt import BaseSecretsManager, ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    all_configs_complete,
    create_yml_files_legacy,
    load_client_config_map_from_file,
    load_strategy_config_map_from_file,
    read_system_configs_from_yml,
)
from hummingbot.client.config.security import Security
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.settings import (
    SCRIPT_STRATEGIES_PATH,
    SCRIPT_STRATEGY_CONF_DIR_PATH,
    STRATEGIES_CONF_DIR_PATH,
    AllConnectorSettings,
)
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.management.console import start_management_console
from hummingbot.core.utils.async_utils import safe_gather


class StrategyRunner:
    """Simplified strategy runner for headless Hummingbot execution."""

    def __init__(self, strategy_name: str, strategy_config: Optional[str] = None,
                 password: Optional[str] = None, headless: bool = True, log_level: str = "INFO"):
        self.strategy_name = strategy_name
        self.strategy_config = strategy_config
        self.password = password or os.environ.get("CONFIG_PASSWORD", "")
        self.headless = headless
        self.log_level = log_level
        self.logger = logging.getLogger(__name__)

    async def run(self):
        """Execute the strategy runner."""
        try:
            self.logger.info(f"Starting Hummingbot with strategy: {self.strategy_name}")
            
            secrets_manager = ETHKeyFileSecretManger(self.password)
            
            if not Security.login(secrets_manager):
                self.logger.error("Invalid password")
                return

            await Security.wait_til_decryption_done()
            await create_yml_files_legacy()
            client_config_map = load_client_config_map_from_file()
            init_logging("hummingbot_logs.yml", client_config_map)
            await read_system_configs_from_yml()

            if self.headless:
                if os.environ.get("MQTT_HOST"):
                    # MQTT enabled - set connection details
                    client_config_map.mqtt_bridge.mqtt_autostart = True
                    client_config_map.mqtt_bridge.mqtt_host = os.environ.get("MQTT_HOST")
                    client_config_map.mqtt_bridge.mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
                else:
                    # No MQTT - disable all MQTT features to bypass headless check
                    client_config_map.mqtt_bridge.mqtt_autostart = True  # Bypass headless check
                    client_config_map.mqtt_bridge.mqtt_logger = False
                    client_config_map.mqtt_bridge.mqtt_notifier = False
                    client_config_map.mqtt_bridge.mqtt_commands = False
                    client_config_map.mqtt_bridge.mqtt_events = False
                    client_config_map.mqtt_bridge.mqtt_external_events = False

            AllConnectorSettings.initialize_paper_trade_settings(
                client_config_map.paper_trade.paper_trade_exchanges
            )

            hb = HummingbotApplication.main_application(
                client_config_map=client_config_map,
                headless_mode=self.headless
            )

            if not await self._load_strategy(hb):
                self.logger.error("Failed to load strategy")
                return

            await self._wait_for_gateway(hb)

            if self.headless:
                self.logger.info(f"Running strategy in headless mode")
                init_logging("hummingbot_logs.yml", hb.client_config_map,
                            override_log_level=self.log_level,
                            strategy_file_path=hb.strategy_file_name)
                await hb.run()
            else:
                tasks = [hb.run()]
                if client_config_map.debug_console:
                    management_port = detect_available_port(8211)
                    tasks.append(start_management_console(locals(), host="localhost", port=management_port))
                await safe_gather(*tasks)

        except Exception as e:
            self.logger.error(f"Error running strategy: {e}", exc_info=True)
            raise

    async def _load_strategy(self, hb: HummingbotApplication) -> bool:
        """Load the strategy configuration."""
        script_path = SCRIPT_STRATEGIES_PATH / f"{self.strategy_name.replace('.py', '')}.py"
        is_script = script_path.exists()
        
        if is_script or self.strategy_name.endswith(".py"):
            return await self._load_script_strategy(hb)
        else:
            return await self._load_yaml_strategy(hb)

    async def _load_script_strategy(self, hb: HummingbotApplication) -> bool:
        """Load a script-based strategy."""
        strategy_name = self.strategy_name.replace(".py", "")
        script_file_path = SCRIPT_STRATEGIES_PATH / f"{strategy_name}.py"

        if not script_file_path.exists():
            self.logger.error(f"Script file not found: {script_file_path}")
            return False

        if self.strategy_config:
            config_path = SCRIPT_STRATEGY_CONF_DIR_PATH / self.strategy_config
            if not config_path.exists():
                self.logger.error(f"Script config file not found: {config_path}")
                return False

        hb.strategy_file_name = self.strategy_config.split(".")[0] if self.strategy_config else strategy_name
        hb.strategy_name = strategy_name

        if self.headless:
            try:
                strategy_module_name = f"scripts.{strategy_name}"
                strategy_module = importlib.import_module(strategy_module_name)
                
                from hummingbot.strategy.strategy_v2_base import StrategyV2ConfigBase
                
                config_class = None
                for name, obj in inspect.getmembers(strategy_module):
                    if inspect.isclass(obj) and name.endswith("Config"):
                        try:
                            if (issubclass(obj, StrategyV2ConfigBase) and 
                                obj is not StrategyV2ConfigBase and
                                obj.__module__ == strategy_module_name):
                                config_class = obj
                                break
                        except TypeError:
                            pass
                
                if not config_class:
                    self.logger.error(f"Could not find config class in {strategy_module_name}")
                    return False
                
                strategy_config = config_class()
                
                success = await hb.trading_core.start_strategy(
                    strategy_name,
                    strategy_config,
                    hb.strategy_file_name + ".py"
                )
                return success
                
            except Exception as e:
                self.logger.error(f"Failed to load script strategy: {e}", exc_info=True)
                return False

        return True

    async def _load_yaml_strategy(self, hb: HummingbotApplication) -> bool:
        """Load a YAML-based strategy."""
        config_filename = self.strategy_name if self.strategy_name.endswith(".yml") else f"{self.strategy_name}.yml"
        hb.strategy_file_name = self.strategy_name.replace(".yml", "")

        try:
            strategy_config = await load_strategy_config_map_from_file(
                STRATEGIES_CONF_DIR_PATH / config_filename
            )
        except FileNotFoundError:
            self.logger.error(f"Strategy config file not found: {STRATEGIES_CONF_DIR_PATH / config_filename}")
            return False
        except Exception as e:
            self.logger.error(f"Error loading strategy config: {e}")
            return False

        strategy_name = (
            strategy_config.strategy
            if isinstance(strategy_config, ClientConfigAdapter)
            else strategy_config.get("strategy").value
        )

        hb.trading_core.strategy_name = strategy_name

        if self.headless:
            success = await hb.trading_core.start_strategy(
                strategy_name,
                strategy_config,
                config_filename
            )
            return success
        else:
            hb.strategy_config_map = strategy_config

        return True

    async def _wait_for_gateway(self, hb: HummingbotApplication):
        """Wait for gateway to be ready if needed."""
        exchange_settings = [
            AllConnectorSettings.get_connector_settings().get(e, None)
            for e in hb.trading_core.connector_manager.connectors.keys()
        ]
        uses_gateway = any([s.uses_gateway_generic_connector() for s in exchange_settings])
        if not uses_gateway:
            return

        try:
            await asyncio.wait_for(
                hb.trading_core.gateway_monitor.ready_event.wait(),
                timeout=GATEWAY_READY_TIMEOUT
            )
        except asyncio.TimeoutError:
            self.logger.error(
                f"Timeout waiting for gateway service. "
                f"Unable to start strategy {hb.trading_core.strategy_name}."
            )
            raise


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run Hummingbot strategy in single-strategy mode (Freqtrading-style)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using command-line arguments
  python hummingbot_run.py --strategy simple_pmm --config pmm_config.yml --password admin

  # Using environment variables (useful in Docker)
  export STRATEGY_NAME=v2_funding_rate_arb
  export STRATEGY_CONFIG=funding_config.yml
  export CONFIG_PASSWORD=mypassword
  python hummingbot_run.py
        """
    )

    parser.add_argument(
        "--strategy", "-s",
        type=str,
        default=os.environ.get("STRATEGY_NAME"),
        help="Strategy name (script name without .py or strategy key from YAML)"
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        default=os.environ.get("STRATEGY_CONFIG"),
        help="Config file name (for script strategies, optional)"
    )

    parser.add_argument(
        "--password", "-p",
        type=str,
        default=os.environ.get("CONFIG_PASSWORD"),
        help="Password for encrypted config files"
    )

    parser.add_argument(
        "--headless",
        type=bool,
        nargs="?",
        const=True,
        default=os.environ.get("HEADLESS_MODE", "true").lower() == "true",
        help="Run in headless mode (default: true)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=os.environ.get("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )

    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.strategy:
        parser.error("--strategy is required (or set STRATEGY_NAME env var)")

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        ev_loop = asyncio.get_running_loop()
    except RuntimeError:
        ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(ev_loop)

    runner = StrategyRunner(
        strategy_name=args.strategy,
        strategy_config=args.config,
        password=args.password,
        headless=args.headless,
        log_level=args.log_level
    )

    try:
        ev_loop.run_until_complete(runner.run())
    except KeyboardInterrupt:
        logging.info("Strategy stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
