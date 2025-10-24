import unittest
from unittest.mock import patch

from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterPerpetualAuth
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth


class TestLighterPerpetualAuth(unittest.TestCase):
    
    def test_perpetual_auth_is_alias(self):
        """Test that LighterPerpetualAuth is an alias for LighterAuth."""
        self.assertIs(LighterPerpetualAuth, LighterAuth)
    
    @patch('hummingbot.connector.exchange.lighter.lighter_auth.SignerClient')
    def test_perpetual_auth_initialization(self, mock_signer):
        """Test that perpetual auth initializes correctly."""
        auth = LighterPerpetualAuth(
            api_key="test_key",
            api_secret="test_secret",
            account_index=123,
            api_key_index=2,
            use_testnet=True
        )
        
        self.assertEqual(auth.account_index, 123)
        self.assertEqual(auth.api_key_index, 2)
        mock_signer.assert_called_once()


if __name__ == "__main__":
    unittest.main()

