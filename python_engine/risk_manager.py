"""
Risk Management Engine for Phase 3 Trading System.
Validates whether trades are allowed before execution.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime


class RiskManager:
    """
    Validates trades against risk limits and constraints.
    
    Enforces position sizes, stop losses, and daily loss limits.
    Has final authority over trade execution.
    """
    
    def __init__(self, config, portfolio_manager, trading_config=None):
        """
        Initialize risk manager.
        
        Args:
            config: Configuration module
            portfolio_manager: Portfolio manager instance
            trading_config: Structured trading config from YAML
        """
        self.config = config
        self.portfolio = portfolio_manager
        self.trading_config = trading_config
        
        # Stop loss tracking per position
        self.stop_losses: Dict[str, float] = {}  # symbol -> stop_price
        
        # Daily loss tracking
        initial_cash = self.trading_config.capital.initial_cash if self.trading_config else self.config.INITIAL_CASH
        self.daily_start_value = initial_cash
        self.daily_start_date = datetime.now().date()
        
    def validate_trade(self, symbol: str, decision: str, quantity: float, 
                      price: float, score: float) -> Tuple[bool, str]:
        """
        Validate whether a trade is allowed.
        
        Args:
            symbol: Stock symbol
            decision: BUY or SELL
            quantity: Trade quantity
            price: Trade price
            score: Stock score
            
        Returns:
            Tuple of (approved, reason)
        """
        # Check daily loss limit
        if self._exceeded_daily_loss_limit():
            return False, "daily_loss_limit_exceeded"
        
        if decision == 'BUY':
            return self._validate_buy(symbol, quantity, price, score)
        elif decision == 'SELL':
            return self._validate_sell(symbol, quantity, price)
        else:
            return False, "invalid_decision"
    
    def _validate_buy(self, symbol: str, quantity: float, price: float, score: float) -> Tuple[bool, str]:
        """
        Validate BUY trade.
        
        Args:
            symbol: Stock symbol
            quantity: Buy quantity
            price: Buy price
            score: Stock score
            
        Returns:
            Tuple of (approved, reason)
        """
        trade_value = quantity * price
        current_portfolio_value = self.portfolio.get_portfolio_value({})
        
        # Check affordability
        if not self.portfolio.can_afford_trade(symbol, quantity, price):
            return False, "insufficient_cash"
        
        # Check position size limit
        max_position_pct = self.trading_config.risk.max_position_size_pct if self.trading_config else self.config.RISK_MAX_POSITION_SIZE
        max_quantity = self.portfolio.get_position_size_limit(price, current_portfolio_value, max_position_pct)
        if quantity > max_quantity:
            return False, f"position_size_exceeds_limit_{max_quantity:.0f}"
        
        # Check total exposure limit
        current_exposure = sum(pos['quantity'] * price for pos in self.portfolio.positions.values())
        new_exposure = current_exposure + trade_value
        max_exposure_pct = self.trading_config.risk.max_total_exposure_pct if self.trading_config else self.config.RISK_MAX_TOTAL_EXPOSURE
        max_exposure = current_portfolio_value * max_exposure_pct
        
        if new_exposure > max_exposure:
            return False, "total_exposure_exceeds_limit"
        
        return True, "approved"
    
    def _validate_sell(self, symbol: str, quantity: float, price: float) -> Tuple[bool, str]:
        """
        Validate SELL trade.
        
        Args:
            symbol: Stock symbol
            quantity: Sell quantity (positive)
            price: Sell price
            
        Returns:
            Tuple of (approved, reason)
        """
        current_pos = self.portfolio.get_position(symbol)
        if not current_pos:
            return False, "no_position_to_sell"
        
        if current_pos['quantity'] < quantity:
            return False, f"insufficient_position_{current_pos['quantity']:.0f}"
        
        # Check stop loss
        if self._violates_stop_loss(symbol, price):
            return False, "stop_loss_triggered"
        
        return True, "approved"
    
    def _violates_stop_loss(self, symbol: str, current_price: float) -> bool:
        """
        Check if selling would violate stop loss.
        
        Args:
            symbol: Stock symbol
            current_price: Current price
            
        Returns:
            True if stop loss violated
        """
        stop_price = self.stop_losses.get(symbol)
        if stop_price is None:
            return False
        
        return current_price <= stop_price
    
    def update_stop_loss(self, symbol: str, entry_price: float) -> None:
        """
        Update stop loss for a position.
        
        Args:
            symbol: Stock symbol
            entry_price: Position entry price
        """
        stop_pct = self.trading_config.risk.stop_loss_pct if self.trading_config else self.config.RISK_STOP_LOSS_PERCENT
        stop_price = entry_price * (1 - stop_pct)
        self.stop_losses[symbol] = stop_price
    
    def remove_stop_loss(self, symbol: str) -> None:
        """
        Remove stop loss for a closed position.
        
        Args:
            symbol: Stock symbol
        """
        self.stop_losses.pop(symbol, None)
    
    def _exceeded_daily_loss_limit(self) -> bool:
        """
        Check if daily loss limit has been exceeded.
        
        Returns:
            True if daily loss limit exceeded
        """
        # Check if it's a new day
        current_date = datetime.now().date()
        if current_date != self.daily_start_date:
            # Reset for new day
            self.daily_start_value = self.portfolio.get_portfolio_value({})
            self.daily_start_date = current_date
            return False
        
        # Calculate current loss
        current_value = self.portfolio.get_portfolio_value({})
        daily_loss = (self.daily_start_value - current_value) / self.daily_start_value
        daily_loss_limit_pct = self.trading_config.risk.daily_loss_limit_pct if self.trading_config else self.config.RISK_DAILY_LOSS_LIMIT
        
        return daily_loss > daily_loss_limit_pct
    
    def get_risk_summary(self) -> Dict:
        """
        Get current risk metrics.
        
        Returns:
            Risk summary dictionary
        """
        current_value = self.portfolio.get_portfolio_value({})
        daily_loss = (self.daily_start_value - current_value) / self.daily_start_value
        daily_loss_limit_pct = self.trading_config.risk.daily_loss_limit_pct if self.trading_config else self.config.RISK_DAILY_LOSS_LIMIT
        max_position_pct = self.trading_config.risk.max_position_size_pct if self.trading_config else self.config.RISK_MAX_POSITION_SIZE
        max_exposure_pct = self.trading_config.risk.max_total_exposure_pct if self.trading_config else self.config.RISK_MAX_TOTAL_EXPOSURE

        return {
            'daily_loss_percent': round(daily_loss * 100, 2),
            'daily_loss_limit_percent': round(daily_loss_limit_pct * 100, 2),
            'stop_losses': self.stop_losses.copy(),
            'max_position_size_percent': round(max_position_pct * 100, 2),
            'max_total_exposure_percent': round(max_exposure_pct * 100, 2)
        }