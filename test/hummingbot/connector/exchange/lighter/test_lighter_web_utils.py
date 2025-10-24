import unittest

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS
from hummingbot.connector.exchange.lighter import lighter_web_utils as web_utils


class TestLighterWebUtils(unittest.TestCase):
    
    def test_rest_url_mainnet(self):
        """Test REST URL construction for mainnet."""
        url = web_utils.rest_url("/api/v1/test", domain="lighter")
        expected = f"{CONSTANTS.BASE_URL}/api/v1/test"
        self.assertEqual(url, expected)
    
    def test_rest_url_testnet(self):
        """Test REST URL construction for testnet."""
        url = web_utils.rest_url("/api/v1/test", domain="lighter_testnet")
        expected = f"{CONSTANTS.TESTNET_BASE_URL}/api/v1/test"
        self.assertEqual(url, expected)
    
    def test_wss_url_mainnet(self):
        """Test WebSocket URL for mainnet."""
        url = web_utils.wss_url(domain="lighter")
        self.assertEqual(url, CONSTANTS.WS_URL)
    
    def test_wss_url_testnet(self):
        """Test WebSocket URL for testnet."""
        url = web_utils.wss_url(domain="lighter_testnet")
        self.assertEqual(url, CONSTANTS.TESTNET_WS_URL)
    
    def test_order_type_to_lighter(self):
        """Test order type conversion."""
        self.assertEqual(web_utils.order_type_to_lighter("limit"), CONSTANTS.ORDER_TYPE_LIMIT)
        self.assertEqual(web_utils.order_type_to_lighter("market"), CONSTANTS.ORDER_TYPE_MARKET)
        self.assertEqual(web_utils.order_type_to_lighter("stop_loss"), CONSTANTS.ORDER_TYPE_STOP_LOSS)
    
    def test_time_in_force_to_lighter(self):
        """Test time in force conversion."""
        self.assertEqual(
            web_utils.time_in_force_to_lighter("ioc"),
            CONSTANTS.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL
        )
        self.assertEqual(
            web_utils.time_in_force_to_lighter("post_only"),
            CONSTANTS.ORDER_TIME_IN_FORCE_POST_ONLY
        )
    
    def test_format_price_for_lighter(self):
        """Test price formatting to integer."""
        price = 2000.5
        price_int = web_utils.format_price_for_lighter(price, decimals=8)
        self.assertEqual(price_int, 200050000000)
    
    def test_format_amount_for_lighter(self):
        """Test amount formatting to integer."""
        amount = 1.5
        amount_int = web_utils.format_amount_for_lighter(amount, decimals=8)
        self.assertEqual(amount_int, 150000000)
    
    def test_parse_price_from_lighter(self):
        """Test price parsing from integer."""
        price_int = 200050000000
        price = web_utils.parse_price_from_lighter(price_int, decimals=8)
        self.assertAlmostEqual(price, 2000.5, places=6)
    
    def test_parse_amount_from_lighter(self):
        """Test amount parsing from integer."""
        amount_int = 150000000
        amount = web_utils.parse_amount_from_lighter(amount_int, decimals=8)
        self.assertAlmostEqual(amount, 1.5, places=6)
    
    def test_create_throttler(self):
        """Test throttler creation."""
        throttler = web_utils.create_throttler()
        self.assertIsNotNone(throttler)
    
    def test_is_exchange_information_valid(self):
        """Test exchange information validation."""
        # Lighter accepts all markets returned by API
        self.assertTrue(web_utils.is_exchange_information_valid({}))
        self.assertTrue(web_utils.is_exchange_information_valid({"test": "data"}))


if __name__ == "__main__":
    unittest.main()

