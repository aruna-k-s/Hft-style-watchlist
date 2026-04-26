import time
from datetime import datetime
from typing import Any, Dict, Optional

from .base_execution import ExecutionEngine

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None


class LiveExecution(ExecutionEngine):
    """Live trading execution engine for Zerodha via Kite API."""

    def __init__(self, config: Any, portfolio_manager: Any, risk_manager: Any):
        super().__init__(config)
        if KiteConnect is None:
            raise ImportError("kiteconnect library is required for live execution")

        self.portfolio = portfolio_manager
        self.risk_manager = risk_manager
        self.mode = config.mode
        self._validate_broker_config()

        broker = self.config.execution.broker
        self.kite = KiteConnect(api_key=broker.api_key)
        if hasattr(self.kite, 'set_access_token'):
            self.kite.set_access_token(broker.access_token)
        self.order_timeout_sec = self.config.execution.order_timeout_sec

    def _validate_broker_config(self) -> None:
        broker = self.config.execution.broker
        if not broker.name or broker.name.lower() != 'zerodha':
            raise ValueError('Live execution only supports Zerodha broker via Kite API')
        missing = [field for field in ['api_key', 'api_secret', 'access_token'] if not getattr(broker, field, None)]
        if missing:
            raise ValueError(f"Missing live broker credentials: {', '.join(missing)}")

    def execute(self, order: Dict[str, Any]) -> Dict[str, Any]:
        symbol = order.get('symbol')
        side = order.get('side')
        quantity = order.get('quantity', 0)
        price = order.get('price', 0.0)

        if not symbol or not isinstance(symbol, str):
            return self._rejected(order, 'invalid_symbol')
        if quantity <= 0:
            return self._rejected(order, 'invalid_quantity')
        if side not in {'BUY', 'SELL'}:
            return self._rejected(order, 'invalid_side')

        order_id = self._place_order(symbol, side, quantity, price)
        if order_id is None:
            return self._rejected(order, 'order_failed')

        status = self._fetch_order_status(order_id)
        if status is None:
            return self._rejected(order, 'status_unknown')

        filled_quantity = status.get('filled_quantity', 0)
        execution_price = status.get('average_price', price)
        order_status = status.get('status', 'UNKNOWN')

        result = 'filled' if filled_quantity > 0 else 'rejected'
        if order_status not in {'COMPLETE', 'TRIGGERED', 'OPEN'} and filled_quantity == 0:
            result = 'rejected'

        self._sync_portfolio()

        return {
            'success': filled_quantity > 0,
            'symbol': symbol,
            'side': side,
            'requested_quantity': quantity,
            'executed_quantity': filled_quantity,
            'requested_price': price,
            'execution_price': execution_price,
            'cash_before': self.portfolio.cash,
            'cash_after': self.portfolio.cash,
            'portfolio_value': self.portfolio.get_portfolio_value({}),
            'result': result,
            'mode': self.mode,
            'status': order_status,
            'broker_order_id': order_id,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
        }

    def _place_order(self, symbol: str, side: str, quantity: float, price: float) -> Optional[str]:
        order_args = {
            'tradingsymbol': symbol,
            'exchange': 'NSE',
            'transaction_type': 'BUY' if side == 'BUY' else 'SELL',
            'quantity': int(quantity),
            'order_type': 'MARKET',
            'product': 'MIS',
            'validity': 'DAY'
        }
        try:
            response = self._retry_api_call(self.kite.place_order, **order_args)
            return response.get('order_id') if isinstance(response, dict) else None
        except Exception:
            return None

    def _fetch_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        try:
            if hasattr(self.kite, 'order_history'):
                history = self._retry_api_call(self.kite.order_history, order_id)
                if isinstance(history, list) and history:
                    return history[-1]
            return self._retry_api_call(self.kite.order_info, order_id)
        except Exception:
            return None

    def _sync_portfolio(self) -> None:
        try:
            positions = self.fetch_positions()
            self.portfolio.positions = {}
            for position in positions:
                symbol = position.get('tradingsymbol') or position.get('symbol')
                qty = float(position.get('quantity', 0))
                avg_price = float(position.get('average_price', 0) or position.get('price', 0))
                if symbol and qty > 0:
                    self.portfolio.positions[symbol] = {
                        'quantity': qty,
                        'avg_price': avg_price,
                        'timestamp': datetime.now()
                    }
        except Exception:
            pass

    def fetch_positions(self) -> Any:
        if hasattr(self.kite, 'positions'):
            return self._retry_api_call(self.kite.positions)
        return []

    def get_positions(self) -> Dict[str, Any]:
        return self.portfolio.positions.copy()

    def get_balance(self) -> float:
        return self.portfolio.cash

    def _retry_api_call(self, func, *args, retries: int = 3, backoff: float = 1.0, **kwargs):
        last_exception = None
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exception = exc
                if attempt < retries - 1:
                    time.sleep(backoff * (2 ** attempt))
                else:
                    raise
        raise last_exception

    def _rejected(self, order: Dict[str, Any], reason: str) -> Dict[str, Any]:
        return {
            'success': False,
            'symbol': order.get('symbol'),
            'side': order.get('side'),
            'requested_quantity': order.get('quantity'),
            'requested_price': order.get('price'),
            'execution_price': None,
            'cash_before': self.portfolio.cash,
            'cash_after': self.portfolio.cash,
            'portfolio_value': self.portfolio.get_portfolio_value({}),
            'result': reason,
            'mode': self.mode,
            'status': 'REJECTED',
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
        }
