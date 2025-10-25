import unittest

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_web_utils as web_utils


class TestLighterPerpetualWebUtils(unittest.TestCase):
    
    def test_rest_url_mainnet(self):
        """Test REST URL construction for perpetual mainnet."""
        url = web_utils.rest_url("/api/v1/test", domain="lighter_perpetual")
        expected = f"{CONSTANTS.PERPETUAL_BASE_URL}/api/v1/test"
        self.assertEqual(url, expected)
    
    def test_rest_url_testnet(self):
        """Test REST URL construction for perpetual testnet."""
        url = web_utils.rest_url("/api/v1/test", domain="lighter_perpetual_testnet")
        expected = f"{CONSTANTS.TESTNET_BASE_URL}/api/v1/test"
        self.assertEqual(url, expected)
    
    def test_wss_url_mainnet(self):
        """Test WebSocket URL for perpetual mainnet."""
        url = web_utils.wss_url(domain="lighter_perpetual")
        self.assertEqual(url, CONSTANTS.PERPETUAL_WS_URL)
    
    def test_wss_url_testnet(self):
        """Test WebSocket URL for perpetual testnet."""
        url = web_utils.wss_url(domain="lighter_perpetual_testnet")
        self.assertEqual(url, CONSTANTS.TESTNET_WS_URL)
    
    def test_create_throttler(self):
        """Test throttler creation for perpetuals."""
        throttler = web_utils.create_throttler()
        self.assertIsNotNone(throttler)
    
    def test_reuses_spot_conversion_functions(self):
        """Test that perpetual connector reuses spot conversion functions."""
        # These should be imported from spot connector
        self.assertTrue(hasattr(web_utils, 'order_type_to_lighter'))
        self.assertTrue(hasattr(web_utils, 'time_in_force_to_lighter'))
        self.assertTrue(hasattr(web_utils, 'format_price_for_lighter'))
        self.assertTrue(hasattr(web_utils, 'format_amount_for_lighter'))
        self.assertTrue(hasattr(web_utils, 'parse_price_from_lighter'))
        self.assertTrue(hasattr(web_utils, 'parse_amount_from_lighter'))


if __name__ == "__main__":
    unittest.main()

