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

# Signal Thresholds
MOMENTUM_THRESHOLD = 0.002  # 0.2% price change over last N ticks
MOMENTUM_WINDOW = 20        # Number of ticks to look back for momentum

VOLUME_SPIKE_THRESHOLD = 2.0  # Factor above rolling average to trigger spike
VOLUME_MA_WINDOW = 20         # Moving average window for volume

SPREAD_TIGHT_THRESHOLD = 0.05  # Consider spread < 0.05 as tight (tradable)

VWAP_DEV_THRESHOLD = 0.02  # 2% deviation from VWAP to signal opportunity

# Scoring Configuration
SCORE_MOMENTUM_UP = 2
SCORE_VOLUME_SPIKE = 2
SCORE_SPREAD_TIGHT = 1
SCORE_VWAP_DEV = 2

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
