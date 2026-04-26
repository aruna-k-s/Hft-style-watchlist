"""
Main orchestrator for the Python signal processing pipeline.
Coordinates data ingestion, signal computation, scoring, and output generation.
"""

import zmq
import json
import struct
import time
import signal
import sys
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, Optional, List, Tuple

from config import *
from signal_engine import SignalEngine
from scoring import ScoringEngine
from strategy import StrategyEngine
from risk_manager import RiskManager
from portfolio import PortfolioManager
from logger import TradeLogger
from execution.execution_factory import get_execution_engine
from execution.config.config_loader import load_trading_config


class WatchlistEngine:
    def __init__(self, trading_config=None):
        self.trading_config = trading_config or load_trading_config()
        self.config_module = sys.modules['config']
        self.signal_engine = SignalEngine(self.config_module)
        self.scoring_engine = ScoringEngine(self.config_module)
        
        # Phase 4: Initialize trading components
        self.portfolio = PortfolioManager(self.trading_config.capital.initial_cash)
        self.logger = TradeLogger(self.config_module.LOG_CSV_FILE, self.config_module.LOG_JSON_FILE)
        self.strategy = StrategyEngine(self.config_module)
        self.risk_manager = RiskManager(self.config_module, self.portfolio, self.trading_config)
        self.execution_engine = get_execution_engine(self.trading_config, self.portfolio, self.risk_manager)
        
        # Ensure output directory exists
        self._ensure_output_directory()
        
        # ZeroMQ setup
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(ZMQ_ENDPOINT)
        self.socket.setsockopt(zmq.SUBSCRIBE, ZMQ_SUBSCRIBE_FILTER)
        
        self.tick_count = 0
        self.last_watchlist_time = 0
        self.should_exit = False
        
        # Phase 2: Stability tracking
        self.stability_tracker: Dict[str, int] = defaultdict(int)  # symbol -> consecutive cycles in top N
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("=" * 80)
        print("   HFT-Style Watchlist: Phase 4 Trading System")
        print("=" * 80)
        print(f"[PHASE 4] Trading Mode: {self.trading_config.mode}")
        print(f"[PHASE 4] Live Trading Enabled: {self.trading_config.enable_live_trading}")
        print(f"[PHASE 4] Initial Cash: ${self.trading_config.capital.initial_cash:,.2f}")
        print(f"[PHASE 4] Risk Limits: Max Position {self.trading_config.risk.max_position_size_pct*100:.1f}%, Total Exposure {self.trading_config.risk.max_total_exposure_pct*100:.1f}%")
        print(f"[PHASE 4] Execution Slippage: {self.trading_config.execution.slippage_pct*100:.2f}%")
        print(f"[PYTHON] Connecting to ZeroMQ at {ZMQ_ENDPOINT}...")
        time.sleep(1)
        print(f"[PYTHON] Phase 2 Features: Rolling Windows, Normalization, Time-Based Scoring")
        print(f"[PYTHON] Stability Filter: {self.config_module.STABILITY_CYCLES_REQUIRED} cycles required")
        print(f"[PYTHON] Waiting for tick data...")
        print("─" * 80)

    def _ensure_output_directory(self) -> None:
        """
        Ensure output directory exists for watchlist.json file.
        Creates directory if it doesn't exist.
        """
        output_dir = os.path.dirname(OUTPUT_FILE)
        
        # If OUTPUT_FILE is just a filename (no path), use current directory
        if not output_dir:
            output_dir = "."
        
        # Create directory if it doesn't exist
        if output_dir != "." and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
                if ENABLE_DEBUG_LOGGING:
                    print(f"[PYTHON] Created output directory: {output_dir}")
            except Exception as e:
                print(f"[PYTHON] Warning: Could not create output directory {output_dir}: {e}")

    def _signal_handler(self, signum, frame):
        """Handle graceful shutdown on SIGINT/SIGTERM."""
        print("\n[PYTHON] Received shutdown signal, exiting gracefully...")
        self.should_exit = True

    def _deserialize_tick(self, message: bytes) -> Optional[Dict]:
        """
        Deserialize binary tick message from ZeroMQ.
        
        Message Format: symbol_len(1) | symbol | price(8) | volume(8) | bid(8) | ask(8) | timestamp(8)
        
        Args:
            message: Raw binary message from ZeroMQ
            
        Returns:
            Dictionary with tick data, or None if deserialization fails
        """
        try:
            if len(message) < 41:  # minimum: 1 (len) + 1 (symbol) + 40 (8*5 doubles/ints)
                return None
            
            offset = 0
            
            # Extract symbol
            symbol_len = message[offset]
            offset += 1
            symbol = message[offset:offset+symbol_len].decode('utf-8')
            offset += symbol_len
            
            # Extract numeric fields
            price, = struct.unpack('d', message[offset:offset+8])
            offset += 8
            volume, = struct.unpack('Q', message[offset:offset+8])
            offset += 8
            bid, = struct.unpack('d', message[offset:offset+8])
            offset += 8
            ask, = struct.unpack('d', message[offset:offset+8])
            offset += 8
            timestamp, = struct.unpack('Q', message[offset:offset+8])
            offset += 8
            
            return {
                'symbol': symbol,
                'price': price,
                'volume': volume,
                'bid': bid,
                'ask': ask,
                'timestamp': timestamp
            }
        except Exception as e:
            if ENABLE_DEBUG_LOGGING:
                print(f"[PYTHON] Deserialization error: {e}")
            return None

    def _process_tick(self, tick: Dict) -> None:
        """
        Process a single tick and add it to the signal engine buffer.
        
        Args:
            tick: Deserialized tick dictionary
        """
        self.signal_engine.add_tick(
            tick['symbol'],
            tick['price'],
            tick['volume'],
            tick['bid'],
            tick['ask'],
            tick['timestamp']
        )
        self.tick_count += 1
        
        # Log statistics periodically
        if self.tick_count % LOG_TICK_EVERY_N == 0:
            symbols = len(self.signal_engine.get_tracked_symbols())
            print(f"[PYTHON] Processed {self.tick_count} ticks from {symbols} symbols")

    def _update_watchlist(self) -> Optional[Dict]:
        """
        Compute watchlist by aggregating signals and scores for all tracked symbols.
        Applies Phase 2 filters: liquidity and stability.
        
        Returns:
            Dictionary with watchlist data, or None if insufficient data
        """
        stock_data = {}
        
        for symbol in self.signal_engine.get_tracked_symbols():
            signals = self.signal_engine.compute_all_signals(symbol)
            if signals is not None:
                # Apply liquidity filter
                if self._passes_liquidity_filter(signals):
                    stock_data[symbol] = {'signals': signals}
        
        # Get ranked stocks
        ranked = self.scoring_engine.rank_stocks(stock_data)
        
        # Apply stability filter
        stable_watchlist = self._apply_stability_filter(ranked)
        
        # Update stability tracker
        self._update_stability_tracker(ranked)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'watchlist': stable_watchlist,
            'total_symbols_tracked': len(self.signal_engine.get_tracked_symbols()),
            'total_symbols_filtered': len(stock_data),
            'total_ticks_processed': self.tick_count
        }

    def _passes_liquidity_filter(self, signals: Dict[str, float]) -> bool:
        """
        Check if stock passes liquidity and tradability filters.
        
        Args:
            signals: Computed signals for the stock
            
        Returns:
            True if stock passes all filters
        """
        # Spread filter
        if signals['spread'] > self.config_module.MAX_SPREAD_THRESHOLD:
            return False
        
        # Volume filter (check recent average volume)
        recent_volumes = [tick['volume'] for tick in list(self.signal_engine.tick_buffer.get(signals.get('symbol', ''), []))[-20:]]
        if recent_volumes:
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            if avg_volume < self.config_module.MIN_VOLUME_THRESHOLD:
                return False
        
        return True

    def _apply_stability_filter(self, ranked: List[Tuple[str, float, str, Dict]]) -> List[Dict]:
        """
        Apply stability filter to ensure stocks have been consistently ranked highly.
        
        Args:
            ranked: List of (symbol, score, reason, signals) tuples
            
        Returns:
            Filtered watchlist that meets stability requirements
        """
        stable_stocks = []
        top_n_symbols = {symbol for symbol, _, _, _ in ranked[:self.config_module.STABILITY_TOP_N]}
        
        for symbol, score, reason, signals in ranked[:self.config_module.WATCHLIST_SIZE]:
            if self.stability_tracker[symbol] >= self.config_module.STABILITY_CYCLES_REQUIRED:
                entry = {
                    'rank': len(stable_stocks) + 1,
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
                
                stable_stocks.append(entry)
        
        return stable_stocks

    def _update_stability_tracker(self, ranked: List[Tuple[str, float, str, Dict]]) -> None:
        """
        Update the stability tracker based on current ranking.
        
        Args:
            ranked: Current ranked list of stocks
        """
        top_n_symbols = {symbol for symbol, _, _, _ in ranked[:self.config_module.STABILITY_TOP_N]}
        
        # Increment counters for stocks in top N, reset others
        for symbol in self.signal_engine.get_tracked_symbols():
            if symbol in top_n_symbols:
                self.stability_tracker[symbol] += 1
            else:
                self.stability_tracker[symbol] = 0

    def _save_watchlist(self, watchlist_data: Dict) -> None:
        """
        Save watchlist to JSON file for integration with dashboards.
        
        Args:
            watchlist_data: Watchlist dictionary with timestamp and entries
        """
        try:
            # Ensure directory exists before writing
            output_dir = os.path.dirname(OUTPUT_FILE)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(watchlist_data, f, indent=2)
            if ENABLE_DEBUG_LOGGING:
                print(f"[PYTHON] Watchlist saved to {os.path.abspath(OUTPUT_FILE)}")
        except Exception as e:
            print(f"[PYTHON] Error saving watchlist to {OUTPUT_FILE}: {e}")

    def _display_watchlist(self, watchlist_data: Dict) -> None:
        """
        Display watchlist in formatted console output.
        
        Args:
            watchlist_data: Watchlist dictionary
        """
        watchlist = watchlist_data['watchlist']
        if not watchlist:
            print("[PYTHON] Watchlist is empty (insufficient data or no stable stocks)")
            return
        
        output = self.scoring_engine.format_watchlist_text(watchlist)
        print(output)
        print(f"[STATUS] {watchlist_data['total_symbols_tracked']} symbols tracked, "
              f"{watchlist_data['total_symbols_filtered']} passed filters, "
              f"{len(watchlist)} stable stocks in watchlist")
        print(f"[TIMESTAMP] {watchlist_data['timestamp']}")
        print("─" * 80)

    def _run_trading_pipeline(self, watchlist: List[Dict]) -> None:
        """
        Run the Phase 3 trading pipeline: strategy → risk → execution → portfolio → logging.
        
        Args:
            watchlist: Current watchlist from Phase 2
        """
        print(f"[TRADING] Running pipeline with {len(watchlist)} watchlist items")
        
        # Update strategy with current positions
        self.strategy.update_positions(self.portfolio.positions)
        
        # Step 1: Generate trade signals (Strategy)
        signals = self.strategy.generate_signals(watchlist)
        
        # Step 2-4: Process each signal through risk → execution → logging
        for signal in signals:
            symbol = signal['symbol']
            decision = signal['decision']
            quantity = signal['quantity']
            price = signal['signals']['current_price']
            score = signal['score']
            
            # Log signal generation
            self.logger.log_signal(symbol, score, signal['reason'], signal['signals'])
            
            # Log trade decision
            self.logger.log_trade_decision(symbol, decision, score, signal['reason'])
            
            # Step 2: Risk validation
            approved, reason = self.risk_manager.validate_trade(symbol, decision, quantity, price, score)
            self.logger.log_risk_check(symbol, approved, reason, quantity, price)
            
            if approved:
                # Step 3: Execute trade
                order = {
                    'symbol': symbol,
                    'side': decision,
                    'quantity': quantity,
                    'price': price
                }
                execution_result = self.execution_engine.execute(order)
                executed_qty = 0

                if execution_result['success']:
                    executed_qty = execution_result['executed_quantity']
                    if decision == 'SELL':
                        executed_qty = -executed_qty  # Negative for sells in logging

                self.logger.log_execution(
                    symbol,
                    executed_qty,
                    execution_result.get('execution_price', price) or price,
                    execution_result.get('cash_before', self.portfolio.cash),
                    execution_result.get('cash_after', self.portfolio.cash),
                    execution_result.get('portfolio_value', self.portfolio.get_portfolio_value({})),
                    self.portfolio.realized_pnl,
                    self.portfolio.unrealized_pnl,
                    execution_result.get('mode', 'paper'),
                    execution_result.get('result', 'unknown'),
                    decision
                )

                if execution_result['success']:
                    # Step 4: Update strategy cooldown
                    if hasattr(self.strategy, 'record_trade'):
                        self.strategy.record_trade(symbol)
                    
                    # Display trade execution
                    print(f"[TRADE] {decision} {executed_qty:.0f} {symbol} @ ${execution_result['execution_price']:.2f}")
        
        # Step 5: Display portfolio status
        self._display_portfolio_status()

    def _display_portfolio_status(self) -> None:
        """
        Display current portfolio status.
        """
        # Get current prices for unrealized PnL calculation
        current_prices = {}
        for symbol in self.signal_engine.get_tracked_symbols():
            signals = self.signal_engine.compute_all_signals(symbol)
            if signals:
                current_prices[symbol] = signals['current_price']
        
        summary = self.portfolio.get_portfolio_summary(current_prices)
        
        print(f"[PORTFOLIO] Cash: ${summary['cash']:,.2f} | "
              f"Value: ${summary['portfolio_value']:,.2f} | "
              f"PnL: ${summary['total_pnl']:,.2f}")
        
        if summary['positions']:
            print("[POSITIONS]")
            for symbol, pos in summary['positions'].items():
                print(f"  {symbol}: {pos['quantity']:.0f} @ ${pos['avg_price']:.2f} | "
                      f"Unrealized: ${pos['unrealized_pnl']:.2f}")
        
        # Log portfolio update
        self.logger.log_portfolio_update(summary)

    def run(self) -> None:
        """
        Main event loop: receive ticks, compute signals, and output watchlist.
        """
        try:
            while not self.should_exit:
                try:
                    # Receive messages with timeout
                    message = self.socket.recv(zmq.NOBLOCK)
                    
                    # Deserialize and process tick
                    tick = self._deserialize_tick(message)
                    if tick:
                        self._process_tick(tick)
                    
                except zmq.Again:
                    # No message available, check if we should update watchlist
                    current_time = time.time()
                    if current_time - self.last_watchlist_time >= REFRESH_INTERVAL_SECONDS:
                        watchlist_data = self._update_watchlist()
                        if watchlist_data and watchlist_data['watchlist']:
                            self._display_watchlist(watchlist_data)
                            self._save_watchlist(watchlist_data)
                            
                            # Phase 3: Run trading pipeline
                            self._run_trading_pipeline(watchlist_data['watchlist'])
                            
                            self.last_watchlist_time = current_time
                    
                    time.sleep(0.01)  # Sleep briefly to avoid busy-waiting
                
        except KeyboardInterrupt:
            print("\n[PYTHON] Interrupted by user")
        except Exception as e:
            print(f"[PYTHON ERROR] {e}")
            raise
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        print("\n[PYTHON] Cleaning up...")
        try:
            self.socket.close()
            self.context.term()
        except Exception as e:
            print(f"[PYTHON] Cleanup error: {e}")
        print("[PYTHON] Shutdown complete")


from execution.core.system_runner import SystemRunner


def main():
    """Entry point for the Python signal engine."""
    runner = SystemRunner()
    runner.run()


if __name__ == "__main__":
    main()
