"""
Scoring engine for ranking stocks based on computed signals.
Implements the scoring logic with configurable weights and thresholds.
Enhanced with Phase 2 features: time-based weighting and normalized features.
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime


class ScoringEngine:
    def __init__(self, config):
        self.config = config

    def _get_market_session(self) -> str:
        """
        Determine current market session based on time of day.
        
        Returns:
            'opening', 'midday', or 'closing'
        """
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        
        # Convert to minutes since midnight for easier comparison
        current_minutes = current_hour * 60 + current_minute
        open_minutes = self.config.MARKET_OPEN_HOUR * 60 + self.config.MARKET_OPEN_MINUTE
        midday_minutes = self.config.MIDDAY_START_HOUR * 60 + self.config.MIDDAY_START_MINUTE
        close_minutes = self.config.MARKET_CLOSE_HOUR * 60 + self.config.MARKET_CLOSE_MINUTE
        
        if current_minutes < midday_minutes:
            return 'opening'
        elif current_minutes < close_minutes:
            return 'midday'
        else:
            return 'closing'

    def _get_session_weights(self, session: str) -> List[float]:
        """
        Get scoring weights for the current market session.
        
        Args:
            session: Market session ('opening', 'midday', 'closing')
            
        Returns:
            List of weights: [momentum, volume_spike, spread_tight, vwap_dev]
        """
        if session == 'opening':
            return self.config.SCORING_WEIGHTS_OPENING
        elif session == 'midday':
            return self.config.SCORING_WEIGHTS_MIDDAY
        else:  # closing
            return self.config.SCORING_WEIGHTS_CLOSING

    def compute_score(self, signals: Dict[str, float]) -> Tuple[float, str]:
        """
        Compute composite score for a stock based on all signals with time-based weighting.
        
        Scoring Rules (Phase 2):
        - Uses normalized features when available for fair comparison
        - Applies time-based weights based on market session
        - Higher absolute normalized values get higher scores
        
        Args:
            signals: Dictionary with computed signals
            
        Returns:
            Tuple of (composite score, reason string)
        """
        session = self._get_market_session()
        weights = self._get_session_weights(session)
        
        score = 0.0
        reasons = []
        
        # Use normalized features if available, otherwise fall back to raw
        momentum_val = signals.get('momentum_normalized', signals['momentum'])
        volume_spike_val = signals.get('volume_spike_normalized', signals['volume_spike'])
        vwap_dev_val = signals.get('vwap_deviation_normalized', signals['vwap_deviation'])
        
        # Momentum scoring (weighted by session)
        abs_momentum = abs(momentum_val)
        if abs_momentum > 0:  # Any significant normalized momentum
            momentum_score = weights[0] * min(abs_momentum, 3.0)  # Cap at 3 std devs
            score += momentum_score
            reasons.append(f"momentum({momentum_val:.2f})")
        
        # Volume spike scoring
        if volume_spike_val > 1.0:  # Above 1 std dev
            volume_score = weights[1] * min(volume_spike_val, 3.0)
            score += volume_score
            reasons.append(f"volume_spike({volume_spike_val:.2f})")
        
        # Spread scoring (tight spread is always good)
        if signals['spread'] < self.config.SPREAD_TIGHT_THRESHOLD:
            spread_score = weights[2]
            score += spread_score
            reasons.append("tight_spread")
        
        # VWAP deviation scoring
        abs_vwap_dev = abs(vwap_dev_val)
        if abs_vwap_dev > 0.5:  # Above 0.5 std dev
            vwap_score = weights[3] * min(abs_vwap_dev, 3.0)
            score += vwap_score
            reasons.append(f"vwap_dev({vwap_dev_val:.2f})")
        
        reason_str = " + ".join(reasons) if reasons else "no_signals"
        return score, reason_str

    def rank_stocks(self, stock_data: Dict[str, Dict]) -> List[Tuple[str, float, str, Dict]]:
        """
        Rank stocks by composite score.
        
        Args:
            stock_data: Dictionary with structure {symbol: {signals: {...}, ...}}
            
        Returns:
            List of tuples: [(symbol, score, reason, signals), ...] sorted by score descending
        """
        ranked = []
        
        for symbol, data in stock_data.items():
            if data['signals'] is not None:
                score, reason = self.compute_score(data['signals'])
                ranked.append((symbol, score, reason, data['signals']))
        
        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def get_top_watchlist(self, stock_data: Dict[str, Dict], top_n: Optional[int] = None) -> List[Dict]:
        """
        Get top N stocks for the watchlist.
        
        Args:
            stock_data: Dictionary with stock data and signals
            top_n: Number of top stocks to return (uses config default if None)
            
        Returns:
            List of watchlist entries with symbol, score, reason, and detailed signals
        """
        if top_n is None:
            top_n = self.config.WATCHLIST_SIZE
        
        ranked = self.rank_stocks(stock_data)
        watchlist = []
        
        for rank, (symbol, score, reason, signals) in enumerate(ranked[:top_n], 1):
            entry = {
                'rank': rank,
                'symbol': symbol,
                'score': round(score, 2),
                'reason': reason,
                'signals': {
                    'momentum': round(signals['momentum'], 6),
                    'volume_spike': round(signals['volume_spike'], 2),
                    'vwap': round(signals['vwap'], 4),
                    'vwap_deviation': round(signals['vwap_deviation'], 6),
                    'spread': round(signals['spread'], 4),
                    'current_price': round(signals['current_price'], 2),
                    'bid': round(signals.get('bid', signals['current_price'] - signals['spread'] / 2), 2),
                    'ask': round(signals.get('ask', signals['current_price'] + signals['spread'] / 2), 2),
                }
            }
            
            # Include normalized features if available
            if 'momentum_normalized' in signals:
                entry['signals']['momentum_normalized'] = round(signals['momentum_normalized'], 2)
                entry['signals']['volume_spike_normalized'] = round(signals['volume_spike_normalized'], 2)
                entry['signals']['vwap_deviation_normalized'] = round(signals['vwap_deviation_normalized'], 2)
            
            watchlist.append(entry)
        
        return watchlist

    def format_watchlist_text(self, watchlist: List[Dict]) -> str:
        """
        Format watchlist for console output with Phase 2 enhancements.
        
        Args:
            watchlist: List of watchlist entries
            
        Returns:
            Formatted string for display
        """
        output = "\n╔═══════════════════════════════════════════════════════════════════════════════╗\n"
        output += "║                     🎯 PHASE 2 ENHANCED WATCHLIST 🎯                        ║\n"
        output += "╠═══════════════════════════════════════════════════════════════════════════════╣\n"
        output += "║ Rank Symbol Score Reason             Momentum Vol.Spike VWAP.Dev Spread Price ║\n"
        output += "╠═══════════════════════════════════════════════════════════════════════════════╣\n"
        
        for entry in watchlist:
            rank = entry['rank']
            symbol = entry['symbol']
            score = entry['score']
            reason = entry['reason'][:15]  # Truncate long reasons
            signals = entry['signals']
            
            momentum = signals['momentum']
            vol_spike = signals['volume_spike']
            vwap_dev = signals['vwap_deviation']
            spread = signals['spread']
            price = signals['current_price']
            
            output += f"║ {rank:2d}   {symbol:6s} {score:5.1f} {reason:15s} {momentum:8.4f} {vol_spike:6.2f} {vwap_dev:8.4f} {spread:6.4f} ${price:7.2f} ║\n"
        
        output += "╚═══════════════════════════════════════════════════════════════════════════════╝\n"
        
        return output
