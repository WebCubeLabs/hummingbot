import unittest
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS


class TestLighterAuth(unittest.TestCase):
    
    def setUp(self):
        self.api_key = "test_api_key_private_key"
        self.api_secret = "test_eth_private_key"
        self.account_index = 123
        self.api_key_index = 2
    
    @patch('hummingbot.connector.exchange.lighter.lighter_auth.SignerClient')
    def test_auth_initialization(self, mock_signer):
        """Test that LighterAuth initializes correctly with SignerClient."""
        auth = LighterAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            account_index=self.account_index,
            api_key_index=self.api_key_index,
            use_testnet=True
        )
        
        self.assertEqual(auth.account_index, self.account_index)
        self.assertEqual(auth.api_key_index, self.api_key_index)
        mock_signer.assert_called_once()
    
    @patch('hummingbot.connector.exchange.lighter.lighter_auth.SignerClient')
    def test_get_base_url_mainnet(self, mock_signer):
        """Test base URL for mainnet."""
        auth = LighterAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            account_index=self.account_index,
            api_key_index=self.api_key_index,
            use_testnet=False
        )
        
        self.assertEqual(auth.get_base_url(), CONSTANTS.BASE_URL)
    
    @patch('hummingbot.connector.exchange.lighter.lighter_auth.SignerClient')
    def test_get_base_url_testnet(self, mock_signer):
        """Test base URL for testnet."""
        auth = LighterAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            account_index=self.account_index,
            api_key_index=self.api_key_index,
            use_testnet=True
        )
        
        self.assertEqual(auth.get_base_url(), CONSTANTS.TESTNET_BASE_URL)
    
    @patch('hummingbot.connector.exchange.lighter.lighter_auth.SignerClient')
    def test_nonce_increments(self, mock_signer):
        """Test that nonce increments correctly."""
        auth = LighterAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            account_index=self.account_index,
            api_key_index=self.api_key_index,
            use_testnet=True
        )
        
        nonce1 = auth.get_next_nonce()
        nonce2 = auth.get_next_nonce()
        nonce3 = auth.get_next_nonce()
        
        self.assertEqual(nonce2, nonce1 + 1)
        self.assertEqual(nonce3, nonce2 + 1)
    
    @patch('hummingbot.connector.exchange.lighter.lighter_auth.SignerClient')
    def test_create_auth_token(self, mock_signer):
        """Test auth token creation."""
        mock_signer_instance = MagicMock()
        mock_signer_instance.create_auth_token_with_expiry.return_value = "test_token"
        mock_signer.return_value = mock_signer_instance
        
        auth = LighterAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            account_index=self.account_index,
            api_key_index=self.api_key_index,
            use_testnet=True
        )
        
        token = auth.create_auth_token(expiry_seconds=3600)
        
        self.assertEqual(token, "test_token")
        mock_signer_instance.create_auth_token_with_expiry.assert_called_once_with(expiry_seconds=3600)


if __name__ == "__main__":
    unittest.main()

