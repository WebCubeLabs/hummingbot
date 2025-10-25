import json
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

from lighter import SignerClient

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class LighterAuth(AuthBase):
    """
    Auth class required by Lighter API with nonce management.
    
    Lighter uses a SignerClient pattern where:
    - API_KEY_PRIVATE_KEY is used to sign transactions
    - ETH_PRIVATE_KEY is the account private key
    - ACCOUNT_INDEX identifies the account
    - API_KEY_INDEX identifies which API key (2-254, 0=desktop, 1=mobile, 255=all)
    - Nonce must be incremented for each transaction per API key
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        account_index: int,
        api_key_index: int = 2,
        use_testnet: bool = False
    ):
        """
        Initialize Lighter authentication.
        
        :param api_key: API key private key for signing (API_KEY_PRIVATE_KEY)
        :param api_secret: ETH private key for the account
        :param account_index: Account index on Lighter
        :param api_key_index: API key index (2-254), defaults to 2
        :param use_testnet: Whether to use testnet
        """
        self._api_key: str = api_key  # API_KEY_PRIVATE_KEY
        self._api_secret: str = api_secret  # ETH_PRIVATE_KEY
        self._account_index: int = account_index
        self._api_key_index: int = api_key_index
        self._use_testnet: bool = use_testnet
        
        # Initialize Lighter SignerClient from SDK
        base_url = self.get_base_url()
        self._signer_client = SignerClient(
            url=base_url,
            private_key=api_key,  # API_KEY_PRIVATE_KEY
            account_index=account_index,
            api_key_index=api_key_index
        )
        
        # Nonce manager per API key
        self._nonce = _NonceManager()
        
        # Cache for auth token
        self._auth_token: Optional[str] = None
        self._auth_token_expiry: float = 0
        
    @property
    def account_index(self) -> int:
        return self._account_index
    
    @property
    def api_key_index(self) -> int:
        return self._api_key_index
    
    def get_base_url(self) -> str:
        """Get the base URL based on testnet/mainnet."""
        return CONSTANTS.TESTNET_BASE_URL if self._use_testnet else CONSTANTS.BASE_URL
    
    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add authentication to REST requests.
        
        For Lighter, most endpoints require an auth token in headers.
        Transaction endpoints (sendTx, sendTxBatch) need signed payloads.
        """
        # Add auth token to headers if available
        if self._auth_token and time.time() < self._auth_token_expiry:
            if request.headers is None:
                request.headers = {}
            request.headers["Authorization"] = f"Bearer {self._auth_token}"
        
        # For POST requests that need signing
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params_post(request.data, request.url)
        
        return request
    
    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Add authentication to WebSocket requests.
        
        Lighter WebSocket requires auth token for private channels.
        """
        if self._auth_token and time.time() < self._auth_token_expiry:
            if request.headers is None:
                request.headers = {}
            request.headers["Authorization"] = f"Bearer {self._auth_token}"
        
        return request
    
    def set_auth_token(self, token: str, expiry_seconds: int = 3600):
        """
        Set the authentication token and its expiry.
        
        :param token: The auth token
        :param expiry_seconds: Token validity in seconds (default 1 hour)
        """
        self._auth_token = token
        self._auth_token_expiry = time.time() + expiry_seconds
    
    def create_auth_token(self, expiry_seconds: int = 3600) -> str:
        """
        Create authentication token using Lighter SignerClient.
        
        :param expiry_seconds: Token validity in seconds (default 1 hour)
        :return: Auth token
        """
        # Use Lighter SDK's SignerClient to create auth token
        token = self._signer_client.create_auth_token_with_expiry(expiry_seconds=expiry_seconds)
        self.set_auth_token(token, expiry_seconds)
        return token
    
    def get_next_nonce(self) -> int:
        """Get the next nonce for signing transactions."""
        return self._nonce.next()
    
    def _sign_create_order_params(self, params: Dict[str, Any], nonce: int) -> Dict[str, Any]:
        """
        Sign create order parameters using Lighter SignerClient.
        
        :param params: Order parameters
        :param nonce: Nonce for the transaction
        :return: Signed transaction payload
        """
        # Use Lighter SDK's SignerClient to sign the order
        signed_tx = self._signer_client.sign_create_order(
            market_id=params.get("market_id"),
            is_buy=params.get("is_buy"),
            base_amount=params.get("base_amount"),
            price=params.get("price"),
            order_type=params.get("order_type", CONSTANTS.ORDER_TYPE_LIMIT),
            time_in_force=params.get("time_in_force", CONSTANTS.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME),
            client_order_index=params.get("client_order_index"),
            nonce=nonce,
        )
        
        return signed_tx
    
    def _sign_cancel_order_params(self, params: Dict[str, Any], nonce: int) -> Dict[str, Any]:
        """
        Sign cancel order parameters using Lighter SignerClient.
        
        :param params: Cancel parameters
        :param nonce: Nonce for the transaction
        :return: Signed transaction payload
        """
        # Use Lighter SDK's SignerClient to sign the cancel order
        signed_tx = self._signer_client.sign_cancel_order(
            market_id=params.get("market_id"),
            order_index=params.get("order_index"),
            nonce=nonce,
        )
        
        return signed_tx
    
    def _sign_cancel_all_orders_params(self, params: Dict[str, Any], nonce: int) -> Dict[str, Any]:
        """
        Sign cancel all orders parameters using Lighter SignerClient.
        
        :param params: Cancel all parameters
        :param nonce: Nonce for the transaction
        :return: Signed transaction payload
        """
        # Use Lighter SDK's SignerClient to sign cancel all
        # The time_in_force determines the type of cancel all:
        # - IOC: ImmediateCancelAll
        # - GTT: ScheduledCancelAll
        # - POST_ONLY: AbortScheduledCancelAll
        time_in_force = params.get("time_in_force", CONSTANTS.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL)
        
        signed_tx = self._signer_client.sign_cancel_all_orders(
            time_in_force=time_in_force,
            nonce=nonce,
        )
        
        return signed_tx
    
    def add_auth_to_params_post(self, params: str, url: str) -> str:
        """
        Add authentication to POST request parameters.
        
        :param params: JSON string of parameters
        :param url: Request URL
        :return: Authenticated JSON string
        """
        nonce = self.get_next_nonce()
        data = json.loads(params) if params is not None else {}
        
        request_params = OrderedDict(data or {})
        
        # Determine request type and sign accordingly
        if "/sendTx" in url:
            if "market_id" in request_params and "base_amount" in request_params:
                # Create order
                payload = self._sign_create_order_params(request_params, nonce)
            elif "order_index" in request_params:
                # Cancel order
                payload = self._sign_cancel_order_params(request_params, nonce)
            else:
                # Default payload
                payload = {"tx": request_params, "nonce": nonce}
        elif "/sendTxBatch" in url:
            # Cancel all orders
            payload = self._sign_cancel_all_orders_params(request_params, nonce)
        else:
            # No signing needed for other endpoints
            payload = request_params
        
        return json.dumps(payload)


class _NonceManager:
    """
    Generates strictly increasing nonces for Lighter transactions.
    Thread-safe for concurrent use.
    """
    
    def __init__(self):
        self._last = 0
        self._lock = threading.Lock()
    
    def next(self) -> int:
        """Get the next nonce, ensuring strict monotonicity."""
        with self._lock:
            self._last += 1
            return self._last
    
    def set(self, value: int):
        """Set the nonce to a specific value (e.g., from API)."""
        with self._lock:
            if value > self._last:
                self._last = value

