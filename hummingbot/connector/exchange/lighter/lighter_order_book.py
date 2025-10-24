from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class LighterOrderBook(OrderBook):
    """Order book implementation for Lighter exchange."""
    
    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: float,
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message.
        
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
        
        # Lighter order book format:
        # {
        #   "bids": [[price, size], ...],
        #   "asks": [[price, size], ...],
        #   "timestamp": ...
        # }
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg.get("trading_pair"),
                "update_id": msg.get("timestamp", int(timestamp * 1000)),
                "bids": [[float(bid[0]), float(bid[1])] for bid in msg.get("bids", [])],
                "asks": [[float(ask[0]), float(ask[1])] for ask in msg.get("asks", [])],
            },
            timestamp=timestamp
        )
    
    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Creates a diff message with the changes in the order book received from the exchange.
        
        :param msg: the changes in the order book
        :param timestamp: the timestamp of the difference
        :param metadata: a dictionary with extra information to add to the difference data
        :return: a diff message with the changes in the order book notified by the exchange
        """
        if metadata:
            msg.update(metadata)
        
        # Lighter order book update format (similar to snapshot)
        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": msg.get("trading_pair"),
                "update_id": msg.get("timestamp", int(timestamp * 1000) if timestamp else 0),
                "bids": [[float(bid[0]), float(bid[1])] for bid in msg.get("bids", [])],
                "asks": [[float(ask[0]), float(ask[1])] for ask in msg.get("asks", [])],
            },
            timestamp=timestamp
        )
    
    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, any],
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Creates a trade message with the information from the trade event sent by the exchange.
        
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)
        
        # Lighter trade format:
        # {
        #   "trade_id": ...,
        #   "market_id": ...,
        #   "price": ...,
        #   "size": ...,
        #   "is_buy": true/false,
        #   "timestamp": ...
        # }
        is_buy = msg.get("is_buy", True)
        trade_type = TradeType.BUY if is_buy else TradeType.SELL
        
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg.get("trading_pair"),
                "trade_type": float(trade_type.value),
                "trade_id": str(msg.get("trade_id", msg.get("id", ""))),
                "price": float(msg.get("price", 0)),
                "amount": float(msg.get("size", msg.get("amount", 0)))
            },
            timestamp=msg.get("timestamp", 0) / 1000.0  # Convert ms to seconds
        )

