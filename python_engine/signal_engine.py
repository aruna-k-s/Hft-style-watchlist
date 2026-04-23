"""
Signal engine for computing technical indicators and features.
Each feature is computed independently for modularity and reusability.
"""

import numpy as np
import pandas as pd
from collections import deque, defaultdict
from typing import Dict, List, Optional, Tuple


class SignalEngine:
    def __init__(self, config):
        self.config = config
        self.tick_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=config.MAX_BUFFER_SIZE))
        self.symbols_tracked = set()
        self.tick_count = 0

    def add_tick(self, symbol: str, price: float, volume: int, bid: float, ask: float, timestamp: int) -> None:
        """
        Add a new tick to the buffer for the given symbol.
        
        Args:
            symbol: Stock ticker symbol
            price: Last traded price
            volume: Volume of the trade
            bid: Best bid price
            ask: Best ask price
            timestamp: Unix timestamp in nanoseconds
        """
        self.tick_buffer[symbol].append({
            'price': price,
            'volume': volume,
            'bid': bid,
            'ask': ask,
            'timestamp': timestamp
        })
        
        if symbol not in self.symbols_tracked:
            self.symbols_tracked.add(symbol)
        
        self.tick_count += 1

    def has_sufficient_data(self, symbol: str) -> bool:
        """Check if we have enough data to compute signals."""
        return len(self.tick_buffer[symbol]) >= self.config.MIN_BUFFER_SIZE

    def compute_momentum(self, symbol: str) -> Optional[float]:
        """
        Calculate momentum as percentage price change over last N ticks.
        
        Momentum = (current_price - price_N_ticks_ago) / price_N_ticks_ago
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Momentum value as a decimal (e.g., 0.02 for +2%), or None if insufficient data
        """
        buffer = self.tick_buffer[symbol]
        
        if len(buffer) < self.config.MOMENTUM_WINDOW:
            return None
        
        current_price = buffer[-1]['price']
        past_price = buffer[-self.config.MOMENTUM_WINDOW]['price']
        
        if past_price <= 0:
            return None
        
        momentum = (current_price - past_price) / past_price
        return momentum

    def compute_volume_spike(self, symbol: str) -> Optional[float]:
        """
        Detect volume spike by comparing current volume to rolling average.
        
        Volume_Spike_Ratio = current_volume / avg_volume
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Volume spike ratio (>1 means above average), or None if insufficient data
        """
        buffer = self.tick_buffer[symbol]
        
        if len(buffer) < self.config.VOLUME_MA_WINDOW:
            return None
        
        recent_volumes = [tick['volume'] for tick in list(buffer)[-self.config.VOLUME_MA_WINDOW:]]
        avg_volume = pd.Series(recent_volumes).mean()
        current_volume = buffer[-1]['volume']
        
        if avg_volume <= 0:
            return None
        
        spike_ratio = current_volume / avg_volume
        return spike_ratio

    def compute_vwap(self, symbol: str) -> Optional[float]:
        """
        Calculate Volume-Weighted Average Price (VWAP).
        
        VWAP = Σ(price * volume) / Σ(volume)
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            VWAP value, or None if insufficient data
        """
        buffer = self.tick_buffer[symbol]
        
        if len(buffer) < self.config.MIN_BUFFER_SIZE:
            return None
        
        dataframe = pd.DataFrame(buffer)
        total_pv = (dataframe['price'] * dataframe['volume']).sum()
        total_volume = dataframe['volume'].sum()
        
        if total_volume <= 0:
            return None
        
        vwap = total_pv / total_volume
        return vwap

    def compute_vwap_deviation(self, symbol: str) -> Optional[float]:
        """
        Calculate deviation from VWAP as potential trading opportunity.
        
        Deviation = (current_price - VWAP) / VWAP
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            VWAP deviation as decimal, or None if insufficient data
        """
        vwap = self.compute_vwap(symbol)
        if vwap is None or vwap <= 0:
            return None
        
        current_price = self.tick_buffer[symbol][-1]['price']
        deviation = (current_price - vwap) / vwap
        return deviation

    def compute_spread(self, symbol: str) -> Optional[float]:
        """
        Calculate bid-ask spread (ask - bid) as liquidity indicator.
        
        Spread = ask_price - bid_price
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Spread value, or None if insufficient data
        """
        buffer = self.tick_buffer[symbol]
        
        if len(buffer) < 1:
            return None
        
        latest_tick = buffer[-1]
        spread = latest_tick['ask'] - latest_tick['bid']
        
        if spread < 0:
            spread = 0.0
        
        return spread

    def compute_all_signals(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Compute all signals for a given symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with all computed signals, or None if insufficient data
        """
        if not self.has_sufficient_data(symbol):
            return None
        
        signals = {}
        
        # Compute all features
        momentum = self.compute_momentum(symbol)
        volume_spike = self.compute_volume_spike(symbol)
        vwap = self.compute_vwap(symbol)
        vwap_dev = self.compute_vwap_deviation(symbol)
        spread = self.compute_spread(symbol)
        
        # Return None if any critical signal is missing
        if any(x is None for x in [momentum, volume_spike, vwap, vwap_dev, spread]):
            return None
        
        signals['momentum'] = momentum
        signals['volume_spike'] = volume_spike
        signals['vwap'] = vwap
        signals['vwap_deviation'] = vwap_dev
        signals['spread'] = spread
        signals['current_price'] = self.tick_buffer[symbol][-1]['price']
        signals['current_volume'] = self.tick_buffer[symbol][-1]['volume']
        
        return signals

    def get_tracked_symbols(self) -> set:
        """Get set of all symbols being tracked."""
        return self.symbols_tracked.copy()

    def get_buffer_size(self, symbol: str) -> int:
        """Get current buffer size for a symbol."""
        return len(self.tick_buffer[symbol])
