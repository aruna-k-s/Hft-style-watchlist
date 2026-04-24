"""
Configuration file for the watchlist engine.
All thresholds, weights, and parameters are defined here for easy tuning.
"""

# ZeroMQ Configuration
ZMQ_ENDPOINT = "tcp://localhost:5555"
ZMQ_SUBSCRIBE_FILTER = b""  # Subscribe to all messages

# Data Buffer Configuration
MAX_BUFFER_SIZE = 500  # Maximum historical ticks per symbol
MIN_BUFFER_SIZE = 10   # Minimum ticks required to compute signals

# Rolling Window Configuration (Phase 2)
ROLLING_WINDOW_SECONDS = 300  # 5 minutes rolling window for statistics
NORMALIZATION_ENABLED = True  # Enable feature normalization

# Signal Thresholds
MOMENTUM_THRESHOLD = 0.002  # 0.2% price change over last N ticks
MOMENTUM_WINDOW = 20        # Number of ticks to look back for momentum

VOLUME_SPIKE_THRESHOLD = 2.0  # Factor above rolling average to trigger spike
VOLUME_MA_WINDOW = 20         # Moving average window for volume

SPREAD_TIGHT_THRESHOLD = 0.05  # Consider spread < 0.05 as tight (tradable)

VWAP_DEV_THRESHOLD = 0.02  # 2% deviation from VWAP to signal opportunity

# Liquidity Filters (Phase 2)
MAX_SPREAD_THRESHOLD = 0.10  # Maximum spread for tradable stocks
MIN_VOLUME_THRESHOLD = 1000  # Minimum average volume for tradable stocks

# Scoring Configuration
SCORE_MOMENTUM_UP = 2
SCORE_VOLUME_SPIKE = 2
SCORE_SPREAD_TIGHT = 1
SCORE_VWAP_DEV = 2

# Time-Based Scoring Weights (Phase 2)
# Weights for different market sessions: [momentum, volume_spike, spread_tight, vwap_dev]
SCORING_WEIGHTS_OPENING = [3, 1, 1, 1]    # 9:30-10:30: Prioritize momentum
SCORING_WEIGHTS_MIDDAY = [1, 1, 1, 3]     # 10:30-15:30: Prioritize VWAP deviation
SCORING_WEIGHTS_CLOSING = [2, 2, 1, 2]    # 15:30-16:00: Balanced

# Market Session Times (24-hour format)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0
MIDDAY_START_HOUR = 10
MIDDAY_START_MINUTE = 30

# Watchlist Stability (Phase 2)
STABILITY_CYCLES_REQUIRED = 3  # Must be in top N for X consecutive cycles
STABILITY_TOP_N = 15  # Consider top 15 for stability check

# Output Configuration
WATCHLIST_SIZE = 10  # Top N stocks to display
REFRESH_INTERVAL_SECONDS = 3  # Update watchlist every 3 seconds
OUTPUT_FILE = "watchlist.json"

# Logging
ENABLE_DEBUG_LOGGING = False
LOG_TICK_EVERY_N = 1000  # Log tick statistics every N ticks

# Performance
NUM_WORKERS = 1  # Number of parallel signal computation workers
BUFFER_POLL_TIMEOUT_MS = 100  # How often to check for new data
