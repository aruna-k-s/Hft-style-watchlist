from datetime import datetime
from typing import Any, Dict

from .base_execution import ExecutionEngine


class PaperExecution(ExecutionEngine):
    """Paper trading execution engine for Phase 4."""

    def __init__(self, config: Any, portfolio_manager: Any, risk_manager: Any):
        super().__init__(config)
        self.portfolio = portfolio_manager
        self.risk_manager = risk_manager
        self.mode = config.mode

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

        execution_price = self._apply_slippage(price, side)
        cash_before = self.portfolio.cash

        if side == 'BUY':
            if not self.portfolio.can_afford_trade(symbol, quantity, execution_price):
                return self._rejected(order, 'insufficient_cash', cash_before)

            self.portfolio.update_position(symbol, quantity, execution_price, timestamp=datetime.now())
            self.risk_manager.update_stop_loss(symbol, execution_price)
            result = 'filled'
        else:
            position = self.portfolio.get_position(symbol)
            if not position or position['quantity'] < quantity:
                return self._rejected(order, 'insufficient_position', cash_before)

            self.portfolio.update_position(symbol, -quantity, execution_price, timestamp=datetime.now())
            if self.portfolio.get_position(symbol) is None:
                self.risk_manager.remove_stop_loss(symbol)
            result = 'filled'

        return self._accepted(order, execution_price, cash_before, result)

    def _apply_slippage(self, price: float, side: str) -> float:
        if side == 'BUY':
            return round(price * (1 + self.config.execution.slippage_pct), 4)
        return round(price * (1 - self.config.execution.slippage_pct), 4)

    def _accepted(self, order: Dict[str, Any], execution_price: float, cash_before: float, result: str) -> Dict[str, Any]:
        portfolio_value = self.portfolio.get_portfolio_value({})
        return {
            'success': True,
            'symbol': order['symbol'],
            'side': order['side'],
            'requested_quantity': order['quantity'],
            'executed_quantity': order['quantity'],
            'requested_price': order['price'],
            'execution_price': execution_price,
            'cash_before': cash_before,
            'cash_after': self.portfolio.cash,
            'portfolio_value': portfolio_value,
            'result': result,
            'mode': self.mode,
            'timestamp': datetime.now().isoformat(),
        }

    def _rejected(self, order: Dict[str, Any], reason: str, cash_before: float = None) -> Dict[str, Any]:
        return {
            'success': False,
            'symbol': order.get('symbol'),
            'side': order.get('side'),
            'requested_quantity': order.get('quantity'),
            'requested_price': order.get('price'),
            'execution_price': None,
            'cash_before': cash_before if cash_before is not None else getattr(self.portfolio, 'cash', None),
            'cash_after': getattr(self.portfolio, 'cash', None),
            'portfolio_value': self.portfolio.get_portfolio_value({}),
            'result': reason,
            'mode': self.mode,
            'timestamp': datetime.now().isoformat(),
        }

    def get_positions(self) -> Dict[str, Any]:
        return self.portfolio.positions.copy()

    def get_balance(self) -> float:
        return self.portfolio.cash
