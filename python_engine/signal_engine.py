"""
Signal engine for computing technical indicators and features.
Each feature is computed independently for modularity and reusability.
Enhanced with Phase 2 features: rolling windows, normalization, and context-aware signals.
"""

import numpy as np
import pandas as pd
from collections import deque, defaultdict
from typing import Dict, List, Optional, Tuple
import time


class SignalEngine:
    def __init__(self, config):
        self.config = config
        # Use time-based rolling window instead of fixed size
        self.tick_buffer: Dict[str, deque] = defaultdict(deque)
        self.symbols_tracked = set()
        self.tick_count = 0
        
        # Rolling statistics for normalization (Phase 2)
        self.rolling_stats: Dict[str, Dict[str, deque]] = defaultdict(lambda: {
            'momentum': deque(maxlen=100),  # Store recent values for mean/std
            'volume_spike': deque(maxlen=100),
            'vwap_deviation': deque(maxlen=100)
        })

    def add_tick(self, symbol: str, price: float, volume: int, bid: float, ask: float, timestamp: int) -> None:
        """
        Add a new tick to the buffer for the given symbol.
        Maintains time-based rolling window by removing old ticks.
        
        Args:
            symbol: Stock ticker symbol
            price: Last traded price
            volume: Volume of the trade
            bid: Best bid price
            ask: Best ask price
            timestamp: Unix timestamp in nanoseconds
        """
        # Convert timestamp to seconds
        timestamp_sec = timestamp / 1e9
        
        # Remove old ticks outside rolling window
        while self.tick_buffer[symbol] and \
              (timestamp_sec - self.tick_buffer[symbol][0]['timestamp'] / 1e9) > self.config.ROLLING_WINDOW_SECONDS:
            self.tick_buffer[symbol].popleft()
        
        # Add new tick
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
        Compute all signals for a given symbol, including normalized features.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with all computed signals and normalized versions, or None if insufficient data
        """
        if not self.has_sufficient_data(symbol):
            return None
        
        signals = {}
        
        # Compute all raw features
        momentum = self.compute_momentum(symbol)
        volume_spike = self.compute_volume_spike(symbol)
        vwap = self.compute_vwap(symbol)
        vwap_dev = self.compute_vwap_deviation(symbol)
        spread = self.compute_spread(symbol)
        
        # Return None if any critical signal is missing
        if any(x is None for x in [momentum, volume_spike, vwap, vwap_dev, spread]):
            return None
        
        # Store raw signals
        signals['momentum'] = momentum
        signals['volume_spike'] = volume_spike
        signals['vwap'] = vwap
        signals['vwap_deviation'] = vwap_dev
        signals['spread'] = spread
        signals['current_price'] = self.tick_buffer[symbol][-1]['price']
        signals['current_volume'] = self.tick_buffer[symbol][-1]['volume']
        
        # Update rolling statistics for normalization
        if self.config.NORMALIZATION_ENABLED:
            self.rolling_stats[symbol]['momentum'].append(momentum)
            self.rolling_stats[symbol]['volume_spike'].append(volume_spike)
            self.rolling_stats[symbol]['vwap_deviation'].append(vwap_dev)
            
            # Compute normalized features
            signals['momentum_normalized'] = self._normalize_feature(symbol, 'momentum', momentum)
            signals['volume_spike_normalized'] = self._normalize_feature(symbol, 'volume_spike', volume_spike)
            signals['vwap_deviation_normalized'] = self._normalize_feature(symbol, 'vwap_deviation', vwap_dev)
        
        return signals

    def _normalize_feature(self, symbol: str, feature_name: str, value: float) -> float:
        """
        Normalize a feature using z-score: (value - rolling_mean) / rolling_std
        
        Args:
            symbol: Stock ticker symbol
            feature_name: Name of the feature to normalize
            value: Raw feature value
            
        Returns:
            Z-score normalized value
        """
        stats_buffer = self.rolling_stats[symbol][feature_name]
        
        if len(stats_buffer) < 10:  # Need minimum samples for stable normalization
            return 0.0
        
        mean_val = np.mean(stats_buffer)
        std_val = np.std(stats_buffer)
        
        if std_val == 0:
            return 0.0
        
        return (value - mean_val) / std_val

    def get_tracked_symbols(self) -> set:
        """Get set of all symbols being tracked."""
        return self.symbols_tracked.copy()

    def get_buffer_size(self, symbol: str) -> int:
        """Get current buffer size for a symbol."""
        return len(self.tick_buffer[symbol])
