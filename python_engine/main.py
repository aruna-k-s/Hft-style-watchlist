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
from typing import Dict, Optional

from config import *
from signal_engine import SignalEngine
from scoring import ScoringEngine


class WatchlistEngine:
    def __init__(self):
        self.config_module = sys.modules['config']
        self.signal_engine = SignalEngine(self.config_module)
        self.scoring_engine = ScoringEngine(self.config_module)
        
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
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("=" * 80)
        print("   HFT-Style Watchlist: Python Signal Engine")
        print("=" * 80)
        print(f"[PYTHON] Connecting to ZeroMQ at {ZMQ_ENDPOINT}...")
        time.sleep(1)
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
        
        Returns:
            Dictionary with watchlist data, or None if insufficient data
        """
        stock_data = {}
        
        for symbol in self.signal_engine.get_tracked_symbols():
            signals = self.signal_engine.compute_all_signals(symbol)
            stock_data[symbol] = {'signals': signals}
        
        # Get top stocks
        watchlist = self.scoring_engine.get_top_watchlist(stock_data, WATCHLIST_SIZE)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'watchlist': watchlist,
            'total_symbols_tracked': len(self.signal_engine.get_tracked_symbols()),
            'total_ticks_processed': self.tick_count
        }

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
            print("[PYTHON] Watchlist is empty (insufficient data)")
            return
        
        output = self.scoring_engine.format_watchlist_text(watchlist)
        print(output)
        print(f"[STATUS] {watchlist_data['total_symbols_tracked']} symbols tracked, "
              f"{watchlist_data['total_ticks_processed']} ticks processed")
        print(f"[TIMESTAMP] {watchlist_data['timestamp']}")
        print("─" * 80)

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


def main():
    """Entry point for the Python signal engine."""
    engine = WatchlistEngine()
    engine.run()


if __name__ == "__main__":
    main()
