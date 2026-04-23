"""
Scoring engine for ranking stocks based on computed signals.
Implements the scoring logic with configurable weights and thresholds.
"""

from typing import Dict, List, Tuple, Optional


class ScoringEngine:
    def __init__(self, config):
        self.config = config

    def compute_score(self, signals: Dict[str, float]) -> float:
        """
        Compute composite score for a stock based on all signals.
        
        Scoring Rules:
        - Strong Momentum (upward or downward) → +2 points
          (We score on absolute magnitude of momentum, capturing both breakouts and sharp declines)
        - Volume spike > threshold → +2 points
        - Tight spread → +1 point
        - VWAP deviation > threshold → +2 points
        
        Args:
            signals: Dictionary with computed signals (momentum, volume_spike, vwap_deviation, spread)
            
        Returns:
            Composite score (higher is better)
        """
        score = 0.0
        
        # Momentum scoring: Score strong directional moves (both up AND down)
        # Absolute value captures both uptrends and sharp declines
        abs_momentum = abs(signals['momentum'])
        if abs_momentum > self.config.MOMENTUM_THRESHOLD:
            score += self.config.SCORE_MOMENTUM_UP
        
        # Volume spike scoring
        if signals['volume_spike'] > self.config.VOLUME_SPIKE_THRESHOLD:
            score += self.config.SCORE_VOLUME_SPIKE
        
        # Spread scoring (tight spread is good for tradability)
        if signals['spread'] < self.config.SPREAD_TIGHT_THRESHOLD:
            score += self.config.SCORE_SPREAD_TIGHT
        
        # VWAP deviation scoring (deviation indicates opportunity)
        # Use absolute value: overvalued OR undervalued both signal opportunity
        abs_vwap_dev = abs(signals['vwap_deviation'])
        if abs_vwap_dev > self.config.VWAP_DEV_THRESHOLD:
            score += self.config.SCORE_VWAP_DEV
        
        return score

    def rank_stocks(self, stock_data: Dict[str, Dict]) -> List[Tuple[str, float, Dict]]:
        """
        Rank stocks by composite score.
        
        Args:
            stock_data: Dictionary with structure {symbol: {signals: {...}, ...}}
            
        Returns:
            List of tuples: [(symbol, score, signals), ...] sorted by score descending
        """
        ranked = []
        
        for symbol, data in stock_data.items():
            if data['signals'] is not None:
                score = self.compute_score(data['signals'])
                ranked.append((symbol, score, data['signals']))
        
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
            List of watchlist entries with symbol, score, and detailed signals
        """
        if top_n is None:
            top_n = self.config.WATCHLIST_SIZE
        
        ranked = self.rank_stocks(stock_data)
        watchlist = []
        
        for rank, (symbol, score, signals) in enumerate(ranked[:top_n], 1):
            entry = {
                'rank': rank,
                'symbol': symbol,
                'score': round(score, 2),
                'signals': {
                    'momentum': round(signals['momentum'], 6),
                    'volume_spike': round(signals['volume_spike'], 2),
                    'vwap': round(signals['vwap'], 4),
                    'vwap_deviation': round(signals['vwap_deviation'], 6),
                    'spread': round(signals['spread'], 4),
                    'current_price': round(signals['current_price'], 2),
                    'bid': round(signals.get('bid', 0), 2) if 'bid' in signals else round(signals['current_price'] - signals['spread'] / 2, 2),
                    'ask': round(signals.get('ask', 0), 2) if 'ask' in signals else round(signals['current_price'] + signals['spread'] / 2, 2),
                }
            }
            watchlist.append(entry)
        
        return watchlist

    def format_watchlist_text(self, watchlist: List[Dict]) -> str:
        """
        Format watchlist for console output.
        
        Args:
            watchlist: List of watchlist entries
            
        Returns:
            Formatted string for display
        """
        output = "\n╔═══════════════════════════════════════════════════════════════════════════════╗\n"
        output += "║                        🎯 TOP WATCHLIST STOCKS 🎯                            ║\n"
        output += "╠═══════════════════════════════════════════════════════════════════════════════╣\n"
        output += "║ Rank  Symbol  Score   Momentum  Vol.Spike  VWAP.Dev  Spread   Price        ║\n"
        output += "╠═══════════════════════════════════════════════════════════════════════════════╣\n"
        
        for entry in watchlist:
            rank = entry['rank']
            symbol = entry['symbol']
            score = entry['score']
            signals = entry['signals']
            momentum = signals['momentum']
            vol_spike = signals['volume_spike']
            vwap_dev = signals['vwap_deviation']
            spread = signals['spread']
            price = signals['current_price']
            
            output += f"║ {rank:2d}    {symbol:6s} {score:5.1f}   {momentum:7.4f}   {vol_spike:6.2f}   {vwap_dev:7.4f}   {spread:6.4f}  ${price:8.2f}  ║\n"
        
        output += "╚═══════════════════════════════════════════════════════════════════════════════╝\n"
        
        return output
