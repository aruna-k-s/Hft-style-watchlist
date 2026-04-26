"""
Portfolio Manager for Phase 3 Trading System.
Maintains full trading state including positions, cash, and PnL calculations.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
import json


class PortfolioManager:
    """
    Manages portfolio state for paper trading.
    
    Tracks positions, cash balance, and computes PnL.
    Single source of truth for all portfolio operations.
    """
    
    def __init__(self, initial_cash: float = 100000.0):
        """
        Initialize portfolio with starting cash.
        
        Args:
            initial_cash: Starting cash balance
        """
        self.cash = initial_cash
        self.positions: Dict[str, Dict] = {}  # symbol -> {'quantity': float, 'avg_price': float, 'timestamp': datetime}
        self.initial_cash = initial_cash
        self.start_time = datetime.now()
        
        # PnL tracking
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        
        # Trade history for daily loss calculation
        self.daily_trades: Dict[str, float] = {}  # date -> realized_pnl
        
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current position for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Position dict with quantity, avg_price, timestamp, or None if no position
        """
        return self.positions.get(symbol)
    
    def update_position(self, symbol: str, quantity: float, price: float, timestamp: Optional[datetime] = None) -> None:
        """
        Update position for a symbol. Handles buys, sells, and position closures.
        
        Args:
            symbol: Stock symbol
            quantity: Positive for buy, negative for sell
            price: Execution price
            timestamp: Trade timestamp
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        current_pos = self.positions.get(symbol, {'quantity': 0.0, 'avg_price': 0.0, 'timestamp': timestamp})
        
        if quantity > 0:  # BUY
            # Calculate new average price
            total_value = current_pos['quantity'] * current_pos['avg_price'] + quantity * price
            new_quantity = current_pos['quantity'] + quantity
            new_avg_price = total_value / new_quantity if new_quantity > 0 else 0.0
            
            self.positions[symbol] = {
                'quantity': new_quantity,
                'avg_price': new_avg_price,
                'timestamp': timestamp
            }
            
        elif quantity < 0:  # SELL
            sell_quantity = abs(quantity)
            
            if current_pos['quantity'] >= sell_quantity:
                # Calculate realized PnL for this sell
                realized_pnl = (price - current_pos['avg_price']) * sell_quantity
                self.realized_pnl += realized_pnl
                
                # Update daily trades
                date_key = timestamp.strftime('%Y-%m-%d')
                self.daily_trades[date_key] = self.daily_trades.get(date_key, 0.0) + realized_pnl
                
                # Update position
                new_quantity = current_pos['quantity'] - sell_quantity
                if new_quantity > 0:
                    self.positions[symbol] = {
                        'quantity': new_quantity,
                        'avg_price': current_pos['avg_price'],
                        'timestamp': timestamp
                    }
                else:
                    # Close position
                    del self.positions[symbol]
                    
        # Update cash
        self.cash -= quantity * price
        
        # Recalculate unrealized PnL
        self._update_unrealized_pnl()
    
    def _update_unrealized_pnl(self) -> None:
        """Recalculate unrealized PnL based on current positions."""
        self.unrealized_pnl = 0.0
        
        # This would need current prices from signal engine
        # For now, we'll calculate it when needed in get_portfolio_value
        
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value including cash and positions.
        
        Args:
            current_prices: Dict of symbol -> current price
            
        Returns:
            Total portfolio value
        """
        position_value = 0.0
        
        for symbol, pos in self.positions.items():
            current_price = current_prices.get(symbol, pos['avg_price'])
            position_value += pos['quantity'] * current_price
            unrealized = (current_price - pos['avg_price']) * pos['quantity']
            self.unrealized_pnl = unrealized  # Update unrealized PnL
            
        return self.cash + position_value
    
    def get_total_pnl(self) -> float:
        """
        Get total PnL (realized + unrealized).
        
        Returns:
            Total PnL
        """
        return self.realized_pnl + self.unrealized_pnl
    
    def get_daily_pnl(self, date: Optional[str] = None) -> float:
        """
        Get realized PnL for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format, or None for today
            
        Returns:
            Daily realized PnL
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        return self.daily_trades.get(date, 0.0)
    
    def get_portfolio_summary(self, current_prices: Dict[str, float]) -> Dict:
        """
        Get complete portfolio summary.
        
        Args:
            current_prices: Dict of symbol -> current price
            
        Returns:
            Portfolio summary dictionary
        """
        portfolio_value = self.get_portfolio_value(current_prices)
        
        return {
            'cash': round(self.cash, 2),
            'portfolio_value': round(portfolio_value, 2),
            'total_pnl': round(self.get_total_pnl(), 2),
            'realized_pnl': round(self.realized_pnl, 2),
            'unrealized_pnl': round(self.unrealized_pnl, 2),
            'positions': {
                symbol: {
                    'quantity': round(pos['quantity'], 2),
                    'avg_price': round(pos['avg_price'], 2),
                    'current_price': round(current_prices.get(symbol, pos['avg_price']), 2),
                    'unrealized_pnl': round((current_prices.get(symbol, pos['avg_price']) - pos['avg_price']) * pos['quantity'], 2)
                }
                for symbol, pos in self.positions.items()
            },
            'position_count': len(self.positions)
        }
    
    def can_afford_trade(self, symbol: str, quantity: float, price: float) -> bool:
        """
        Check if portfolio can afford a trade.
        
        Args:
            symbol: Stock symbol
            quantity: Trade quantity (positive for buy)
            price: Trade price
            
        Returns:
            True if trade is affordable
        """
        cost = quantity * price
        return self.cash >= cost
    
    def get_position_size_limit(self, price: float, total_capital: float, max_position_pct: float = None) -> float:
        """
        Calculate maximum position size based on risk limits.
        
        Args:
            price: Stock price
            total_capital: Current total portfolio value
            max_position_pct: Optional override for maximum position percentage
            
        Returns:
            Maximum quantity allowed
        """
        if max_position_pct is None:
            from config import RISK_MAX_POSITION_SIZE
            max_position_pct = RISK_MAX_POSITION_SIZE

        max_position_value = total_capital * max_position_pct
        return max_position_value / price if price > 0 else 0.0