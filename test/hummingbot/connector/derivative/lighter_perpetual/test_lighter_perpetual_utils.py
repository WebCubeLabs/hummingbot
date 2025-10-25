import unittest

from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_utils import (
    LighterPerpetualConfigMap,
    LighterPerpetualTestnetConfigMap,
    DEFAULT_FEES,
    EXAMPLE_PAIR,
)


class TestLighterPerpetualUtils(unittest.TestCase):
    
    def test_default_fees(self):
        """Test default fee configuration for perpetuals."""
        self.assertIsNotNone(DEFAULT_FEES)
        # Premium account fees: 0.2 bps maker, 2 bps taker
        self.assertGreater(DEFAULT_FEES.taker_percent_fee_decimal, 0)
    
    def test_example_pair(self):
        """Test example trading pair for perpetuals."""
        self.assertEqual(EXAMPLE_PAIR, "ETH-USDC")
    
    def test_perpetual_config_map_structure(self):
        """Test LighterPerpetualConfigMap has required fields."""
        config = LighterPerpetualConfigMap.model_construct()
        
        # Check that required fields exist
        self.assertTrue(hasattr(config, 'lighter_perpetual_api_key'))
        self.assertTrue(hasattr(config, 'lighter_perpetual_api_secret'))
        self.assertTrue(hasattr(config, 'lighter_perpetual_account_index'))
        self.assertTrue(hasattr(config, 'lighter_perpetual_api_key_index'))
    
    def test_perpetual_testnet_config_map_structure(self):
        """Test LighterPerpetualTestnetConfigMap has required fields."""
        config = LighterPerpetualTestnetConfigMap.model_construct()
        
        # Check that required fields exist
        self.assertTrue(hasattr(config, 'lighter_perpetual_testnet_api_key'))
        self.assertTrue(hasattr(config, 'lighter_perpetual_testnet_api_secret'))
        self.assertTrue(hasattr(config, 'lighter_perpetual_testnet_account_index'))
        self.assertTrue(hasattr(config, 'lighter_perpetual_testnet_api_key_index'))


if __name__ == "__main__":
    unittest.main()

