"""
Execution Engine for Phase 3 Trading System.
Simulates order execution in paper trading mode.
"""

from typing import Dict, Optional
from datetime import datetime


class ExecutionEngine:
    """
    Simulates trade execution in paper trading mode.
    
    Executes approved trades and updates portfolio state.
    No real broker integration - pure simulation.
    """
    
    def __init__(self, config, portfolio_manager, risk_manager):
        """
        Initialize execution engine.
        
        Args:
            config: Configuration module
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
        """
        self.config = config
        self.portfolio = portfolio_manager
        self.risk = risk_manager
        
    def execute_trade(self, symbol: str, decision: str, quantity: float, 
                     price: float) -> Dict[str, any]:
        """
        Execute a trade in paper trading mode.
        
        Args:
            symbol: Stock symbol
            decision: BUY or SELL
            quantity: Trade quantity
            price: Execution price
            
        Returns:
            Execution result dictionary
        """
        # Apply slippage (0 in Phase 3)
        execution_price = price * (1 + self.config.EXECUTION_SLIPPAGE)
        
        # Record cash before trade
        cash_before = self.portfolio.cash
        
        # Execute the trade
        if decision == 'BUY':
            result = self._execute_buy(symbol, quantity, execution_price)
        elif decision == 'SELL':
            result = self._execute_sell(symbol, quantity, execution_price)
        else:
            result = {
                'success': False,
                'reason': 'invalid_decision',
                'executed_quantity': 0,
                'execution_price': 0
            }
        
        # Update risk manager
        if result['success']:
            if decision == 'BUY':
                self.risk.update_stop_loss(symbol, execution_price)
            elif decision == 'SELL' and result.get('closed_position', False):
                self.risk.remove_stop_loss(symbol)
        
        # Add execution details
        result.update({
            'symbol': symbol,
            'decision': decision,
            'requested_quantity': quantity,
            'requested_price': price,
            'cash_before': cash_before,
            'cash_after': self.portfolio.cash,
            'portfolio_value': self.portfolio.get_portfolio_value({}),
            'timestamp': datetime.now().isoformat()
        })
        
        return result
    
    def _execute_buy(self, symbol: str, quantity: float, price: float) -> Dict[str, any]:
        """
        Execute BUY order.
        
        Args:
            symbol: Stock symbol
            quantity: Buy quantity
            price: Execution price
            
        Returns:
            Execution result
        """
        cost = quantity * price
        
        if self.portfolio.cash < cost:
            return {
                'success': False,
                'reason': 'insufficient_cash',
                'executed_quantity': 0,
                'execution_price': price
            }
        
        # Update portfolio
        self.portfolio.update_position(symbol, quantity, price)
        
        return {
            'success': True,
            'reason': 'executed',
            'executed_quantity': quantity,
            'execution_price': price,
            'closed_position': False
        }
    
    def _execute_sell(self, symbol: str, quantity: float, price: float) -> Dict[str, any]:
        """
        Execute SELL order.
        
        Args:
            symbol: Stock symbol
            quantity: Sell quantity
            price: Execution price
            
        Returns:
            Execution result
        """
        current_pos = self.portfolio.get_position(symbol)
        
        if not current_pos:
            return {
                'success': False,
                'reason': 'no_position',
                'executed_quantity': 0,
                'execution_price': price
            }
        
        if current_pos['quantity'] < quantity:
            return {
                'success': False,
                'reason': 'insufficient_position',
                'executed_quantity': 0,
                'execution_price': price
            }
        
        # Update portfolio (negative quantity for sell)
        self.portfolio.update_position(symbol, -quantity, price)
        
        # Check if position was closed
        new_pos = self.portfolio.get_position(symbol)
        closed_position = new_pos is None or new_pos['quantity'] == 0
        
        return {
            'success': True,
            'reason': 'executed',
            'executed_quantity': quantity,
            'execution_price': price,
            'closed_position': closed_position
        }
    
    def get_execution_summary(self) -> Dict:
        """
        Get execution engine summary.
        
        Returns:
            Summary dictionary
        """
        return {
            'paper_mode': self.config.PAPER_MODE,
            'slippage': self.config.EXECUTION_SLIPPAGE,
            'last_portfolio_value': self.portfolio.get_portfolio_value({})
        }