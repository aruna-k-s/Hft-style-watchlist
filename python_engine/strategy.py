"""
Strategy Engine for Phase 3 Trading System.
Converts watchlist signals into actionable trade decisions.
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import time


class StrategyEngine:
    """
    Generates trade decisions based on deterministic rules.
    
    Converts ranked watchlist into BUY/SELL/HOLD signals with cooldown logic.
    Only decides WHAT to trade, not HOW MUCH or IF ALLOWED.
    """
    
    def __init__(self, config):
        """
        Initialize strategy engine.
        
        Args:
            config: Configuration module
        """
        self.config = config
        
        # Track last trade time per symbol for cooldown
        self.last_trade_time: Dict[str, datetime] = {}
        
        # Track current positions (will be synced from portfolio)
        self.current_positions: Dict[str, Dict] = {}
        
    def update_positions(self, positions: Dict[str, Dict]) -> None:
        """
        Update current positions from portfolio manager.
        
        Args:
            positions: Current positions dictionary
        """
        self.current_positions = positions.copy()
    
    def generate_signals(self, watchlist: List[Dict]) -> List[Dict]:
        """
        Generate trade signals from watchlist.
        
        Args:
            watchlist: List of watchlist entries with scores and signals
            
        Returns:
            List of trade signals with decisions
        """
        signals = []
        
        for entry in watchlist:
            symbol = entry['symbol']
            score = entry['score']
            signals_dict = entry['signals']
            
            decision, reason = self._decide_trade(symbol, score, signals_dict)
            
            if decision != 'HOLD':
                signal_entry = {
                    'symbol': symbol,
                    'decision': decision,
                    'score': score,
                    'reason': reason,
                    'signals': signals_dict,
                    'quantity': self._calculate_quantity(symbol, signals_dict.get('current_price', 0))
                }
                signals.append(signal_entry)
        
        return signals
    
    def _decide_trade(self, symbol: str, score: float, signals: Dict[str, float]) -> Tuple[str, str]:
        """
        Decide whether to BUY, SELL, or HOLD a stock.
        
        Args:
            symbol: Stock symbol
            score: Computed score
            signals: Signal dictionary
            
        Returns:
            Tuple of (decision, reason)
        """
        # Check cooldown
        if self._is_on_cooldown(symbol):
            return 'HOLD', 'cooldown_active'
        
        # Check if already in position
        has_position = symbol in self.current_positions
        
        # BUY logic
        if not has_position and self._should_buy(score, signals):
            return 'BUY', f'score_{score:.1f}_momentum_{signals.get("momentum", 0):.4f}'
        
        # SELL logic
        elif has_position and self._should_sell(score, signals):
            return 'SELL', f'score_dropped_{score:.1f}_momentum_{signals.get("momentum", 0):.4f}'
        
        return 'HOLD', 'no_signal'
    
    def _should_buy(self, score: float, signals: Dict[str, float]) -> bool:
        """
        Determine if stock should be bought.
        
        Args:
            score: Stock score
            signals: Signal dictionary
            
        Returns:
            True if should buy
        """
        # Score threshold
        if score < self.config.STRATEGY_SCORE_THRESHOLD:
            return False
        
        # Momentum threshold
        momentum = signals.get('momentum', 0)
        if momentum < self.config.STRATEGY_MOMENTUM_THRESHOLD:
            return False
        
        return True
    
    def _should_sell(self, score: float, signals: Dict[str, float]) -> bool:
        """
        Determine if stock should be sold.
        
        Args:
            score: Stock score
            signals: Signal dictionary
            
        Returns:
            True if should sell
        """
        # Score dropped below threshold
        if score < self.config.STRATEGY_SCORE_THRESHOLD * 0.5:  # Sell at half the buy threshold
            return True
        
        # Momentum reversed
        momentum = signals.get('momentum', 0)
        if momentum < -self.config.STRATEGY_MOMENTUM_THRESHOLD:
            return True
        
        return False
    
    def _calculate_quantity(self, symbol: str, price: float) -> float:
        """
        Calculate trade quantity (placeholder - will be validated by risk manager).
        
        Args:
            symbol: Stock symbol
            price: Current price
            
        Returns:
            Proposed quantity
        """
        # For now, use a smaller base quantity to work with risk limits
        # In a real system, this could be based on Kelly criterion, etc.
        base_quantity = 50  # 50 shares (reduced from 100)
        
        # Adjust based on price (round lots)
        if price > 0:
            # Ensure we don't go below minimum
            quantity = max(base_quantity, int(500 / price))  # At least $500 worth (reduced from $1000)
            return quantity
        
        return 0
    
    def _is_on_cooldown(self, symbol: str) -> bool:
        """
        Check if symbol is on cooldown from last trade.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if on cooldown
        """
        last_trade = self.last_trade_time.get(symbol)
        if last_trade is None:
            return False
        
        cooldown_end = last_trade + timedelta(seconds=self.config.STRATEGY_COOLDOWN_SECONDS)
        return datetime.now() < cooldown_end
    
    def record_trade(self, symbol: str) -> None:
        """
        Record that a trade was executed for cooldown tracking.
        
        Args:
            symbol: Stock symbol
        """
        self.last_trade_time[symbol] = datetime.now()
    
    def get_cooldown_status(self, symbol: str) -> Optional[float]:
        """
        Get remaining cooldown time in seconds.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Remaining cooldown seconds, or None if not on cooldown
        """
        last_trade = self.last_trade_time.get(symbol)
        if last_trade is None:
            return None
        
        cooldown_end = last_trade + timedelta(seconds=self.config.STRATEGY_COOLDOWN_SECONDS)
        remaining = (cooldown_end - datetime.now()).total_seconds()
        
        return max(0, remaining) if remaining > 0 else None