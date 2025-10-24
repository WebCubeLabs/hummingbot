from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, SecretStr, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Lighter fees:
# Standard account: fee-less (0% maker, 0% taker)
# Premium account: 0.2 bps maker (0.0002%), 2 bps taker (0.002%)
# Default to Premium account fees for conservative estimation
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00002"),  # 0.2 bps
    taker_percent_fee_decimal=Decimal("0.0002"),   # 2 bps
    buy_percent_fee_deducted_from_returns=True
)

CENTRALIZED = False

EXAMPLE_PAIR = "ETH-USDC"

BROKER_ID = "HBOT"


def validate_int(value: str, min_val: int = None, max_val: int = None) -> Optional[str]:
    """
    Validate that a string can be converted to an integer within bounds.
    
    :param value: String to validate
    :param min_val: Minimum allowed value
    :param max_val: Maximum allowed value
    :return: Error message if invalid, None if valid
    """
    try:
        int_val = int(value)
        if min_val is not None and int_val < min_val:
            return f"Value must be at least {min_val}"
        if max_val is not None and int_val > max_val:
            return f"Value must be at most {max_val}"
    except ValueError:
        return "Value must be an integer"
    return None


class LighterConfigMap(BaseConnectorConfigMap):
    """Configuration map for Lighter mainnet connector."""
    
    connector: str = "lighter"
    
    lighter_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter API key private key (API_KEY_PRIVATE_KEY)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    lighter_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Ethereum wallet private key (ETH_PRIVATE_KEY)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    lighter_account_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter account index (ACCOUNT_INDEX)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    lighter_api_key_index: int = Field(
        default=2,
        json_schema_extra={
            "prompt": "Enter your Lighter API key index (2-254, default: 2)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    @field_validator("lighter_api_key_index", mode="before")
    @classmethod
    def validate_api_key_index(cls, v):
        """Validate API key index is within valid range (2-254)."""
        if isinstance(v, str):
            error = validate_int(v, min_val=2, max_val=254)
            if error:
                raise ValueError(f"API key index: {error}")
            v = int(v)
        if not isinstance(v, int) or v < 2 or v > 254:
            raise ValueError("API key index must be between 2 and 254")
        return v
    
    @field_validator("lighter_account_index", mode="before")
    @classmethod
    def validate_account_index(cls, v):
        """Validate account index is a positive integer."""
        if isinstance(v, str):
            error = validate_int(v, min_val=0)
            if error:
                raise ValueError(f"Account index: {error}")
            v = int(v)
        if not isinstance(v, int) or v < 0:
            raise ValueError("Account index must be a positive integer")
        return v


KEYS = LighterConfigMap.model_construct()

OTHER_DOMAINS = ["lighter_testnet"]
OTHER_DOMAINS_PARAMETER = {"lighter_testnet": "lighter_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"lighter_testnet": "ETH-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"lighter_testnet": [0.00002, 0.0002]}


class LighterTestnetConfigMap(BaseConnectorConfigMap):
    """Configuration map for Lighter testnet connector."""
    
    connector: str = "lighter_testnet"
    
    lighter_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key private key (API_KEY_PRIVATE_KEY)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    lighter_testnet_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Ethereum wallet private key for testnet (ETH_PRIVATE_KEY)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    lighter_testnet_account_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Lighter testnet account index (ACCOUNT_INDEX)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    lighter_testnet_api_key_index: int = Field(
        default=2,
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key index (2-254, default: 2)",
            "is_secure": False,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    
    model_config = ConfigDict(title="lighter_testnet")
    
    @field_validator("lighter_testnet_api_key_index", mode="before")
    @classmethod
    def validate_api_key_index(cls, v):
        """Validate API key index is within valid range (2-254)."""
        if isinstance(v, str):
            error = validate_int(v, min_val=2, max_val=254)
            if error:
                raise ValueError(f"API key index: {error}")
            v = int(v)
        if not isinstance(v, int) or v < 2 or v > 254:
            raise ValueError("API key index must be between 2 and 254")
        return v
    
    @field_validator("lighter_testnet_account_index", mode="before")
    @classmethod
    def validate_account_index(cls, v):
        """Validate account index is a positive integer."""
        if isinstance(v, str):
            error = validate_int(v, min_val=0)
            if error:
                raise ValueError(f"Account index: {error}")
            v = int(v)
        if not isinstance(v, int) or v < 0:
            raise ValueError("Account index must be a positive integer")
        return v


OTHER_DOMAINS_KEYS = {"lighter_testnet": LighterTestnetConfigMap.model_construct()}

