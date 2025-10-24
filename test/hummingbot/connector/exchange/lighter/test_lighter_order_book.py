import unittest
from decimal import Decimal

from hummingbot.connector.exchange.lighter.lighter_order_book import LighterOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestLighterOrderBook(unittest.TestCase):
    
    def test_snapshot_message_from_exchange(self):
        """Test creating snapshot message from exchange data."""
        msg = {
            "trading_pair": "ETH-USDC",
            "timestamp": 1234567890000,
            "bids": [[2000.0, 1.5], [1999.0, 2.0]],
            "asks": [[2001.0, 1.0], [2002.0, 1.5]],
        }
        timestamp = 1234567890.0
        
        snapshot = LighterOrderBook.snapshot_message_from_exchange(
            msg, timestamp, metadata={"trading_pair": "ETH-USDC"}
        )
        
        self.assertEqual(snapshot.type, OrderBookMessageType.SNAPSHOT)
        self.assertEqual(snapshot.content["trading_pair"], "ETH-USDC")
        self.assertEqual(len(snapshot.content["bids"]), 2)
        self.assertEqual(len(snapshot.content["asks"]), 2)
        self.assertEqual(snapshot.content["bids"][0][0], 2000.0)
        self.assertEqual(snapshot.content["bids"][0][1], 1.5)
    
    def test_diff_message_from_exchange(self):
        """Test creating diff message from exchange data."""
        msg = {
            "trading_pair": "ETH-USDC",
            "timestamp": 1234567890000,
            "bids": [[2000.0, 1.5]],
            "asks": [[2001.0, 1.0]],
        }
        timestamp = 1234567890.0
        
        diff = LighterOrderBook.diff_message_from_exchange(
            msg, timestamp, metadata={"trading_pair": "ETH-USDC"}
        )
        
        self.assertEqual(diff.type, OrderBookMessageType.DIFF)
        self.assertEqual(diff.content["trading_pair"], "ETH-USDC")
    
    def test_trade_message_from_exchange(self):
        """Test creating trade message from exchange data."""
        msg = {
            "trading_pair": "ETH-USDC",
            "trade_id": "12345",
            "price": 2000.0,
            "size": 1.5,
            "is_buy": True,
            "timestamp": 1234567890000,
        }
        
        trade = LighterOrderBook.trade_message_from_exchange(
            msg, metadata={"trading_pair": "ETH-USDC"}
        )
        
        self.assertEqual(trade.type, OrderBookMessageType.TRADE)
        self.assertEqual(trade.content["trading_pair"], "ETH-USDC")
        self.assertEqual(trade.content["trade_id"], "12345")
        self.assertEqual(trade.content["price"], 2000.0)
        self.assertEqual(trade.content["amount"], 1.5)


if __name__ == "__main__":
    unittest.main()

