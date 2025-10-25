import unittest

from hummingbot.connector.exchange.lighter.lighter_utils import (
    LighterConfigMap,
    LighterTestnetConfigMap,
    validate_int,
    DEFAULT_FEES,
    EXAMPLE_PAIR,
)


class TestLighterUtils(unittest.TestCase):
    
    def test_validate_int_valid(self):
        """Test integer validation with valid input."""
        self.assertIsNone(validate_int("123"))
        self.assertIsNone(validate_int("0"))
        self.assertIsNone(validate_int("999"))
    
    def test_validate_int_invalid(self):
        """Test integer validation with invalid input."""
        error = validate_int("abc")
        self.assertIsNotNone(error)
        self.assertIn("integer", error.lower())
    
    def test_validate_int_with_bounds(self):
        """Test integer validation with min/max bounds."""
        # Within bounds
        self.assertIsNone(validate_int("5", min_val=1, max_val=10))
        
        # Below minimum
        error = validate_int("0", min_val=1, max_val=10)
        self.assertIsNotNone(error)
        self.assertIn("at least", error.lower())
        
        # Above maximum
        error = validate_int("11", min_val=1, max_val=10)
        self.assertIsNotNone(error)
        self.assertIn("at most", error.lower())
    
    def test_default_fees(self):
        """Test default fee configuration."""
        self.assertIsNotNone(DEFAULT_FEES)
        # Premium account fees: 0.2 bps maker, 2 bps taker
        self.assertGreater(DEFAULT_FEES.taker_percent_fee_decimal, 0)
    
    def test_example_pair(self):
        """Test example trading pair."""
        self.assertEqual(EXAMPLE_PAIR, "ETH-USDC")
    
    def test_lighter_config_map_structure(self):
        """Test LighterConfigMap has required fields."""
        config = LighterConfigMap.model_construct()
        
        # Check that required fields exist
        self.assertTrue(hasattr(config, 'lighter_api_key'))
        self.assertTrue(hasattr(config, 'lighter_api_secret'))
        self.assertTrue(hasattr(config, 'lighter_account_index'))
        self.assertTrue(hasattr(config, 'lighter_api_key_index'))
    
    def test_lighter_testnet_config_map_structure(self):
        """Test LighterTestnetConfigMap has required fields."""
        config = LighterTestnetConfigMap.model_construct()
        
        # Check that required fields exist
        self.assertTrue(hasattr(config, 'lighter_testnet_api_key'))
        self.assertTrue(hasattr(config, 'lighter_testnet_api_secret'))
        self.assertTrue(hasattr(config, 'lighter_testnet_account_index'))
        self.assertTrue(hasattr(config, 'lighter_testnet_api_key_index'))


if __name__ == "__main__":
    unittest.main()

