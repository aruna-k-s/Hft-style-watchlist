# HFT-Style Automated Watchlist Generator

A production-quality, low-latency stock watchlist system using C++ for market data ingestion, Python for signal processing, and ZeroMQ for high-speed inter-process communication.

**Phase 2 Enhancement:** Advanced signal intelligence with context-aware signals, feature normalization, time-based scoring, and stability filtering for improved decision quality.

**Phase 3 Enhancement:** Complete trading system with strategy engine, risk management, portfolio tracking, and execution simulation.

**Phase 4 Enhancement:** Real-time market data integration with Upstox WebSocket API, protobuf decoding, and production-safe reconnection handling.

**Design Principle:** Modular, clean separation of concerns with minimal latency overhead. Perfect for learning real-time trading systems architecture.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 2 Enhancements](#phase-2-enhancements)
3. [Phase 3: Complete Trading System](#phase-3-complete-trading-system)
4. [Phase 4: Production Trading System](#phase-4-production-trading-system)
5. [System Requirements](#system-requirements)
6. [Quick Start (Docker)](#quick-start-docker)
7. [Build Instructions](#build-instructions)
8. [Configuration](#configuration)
9. [Running the System](#running-the-system)
10. [Output Format](#output-format)
11. [Troubleshooting](#troubleshooting)
12. [Project Structure](#project-structure)
13. [Performance Notes](#performance-notes)

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Market Data Flow                             │
└─────────────────────────────────────────────────────────────────┘

 ┌──────────────────┐
 │  Tick Simulator  │  (C++) Generates realistic mock market ticks
 │  (or Real API)   │  with random walk price movement & volume spikes
 └────────┬─────────┘
          │ 100 symbols, ~500 ticks/sec
          ▼
 ┌──────────────────┐
 │  Ingestion       │  (C++) Validates, deduplicates, maintains
 │  Engine          │  latest tick per symbol (O(1) updates)
 └────────┬─────────┘
          │ Binary format
          ▼
 ┌──────────────────┐
 │  ZeroMQ PUB      │  Fast, async message broadcast
 │  (tcp://5555)    │  (~500 msgs/sec, negligible latency)
 └────────┬─────────┘
          │
          ▼
 ┌──────────────────┐
 │  ZeroMQ SUB      │  (Python) Receives tick stream
 │  Subscriber      │  Non-blocking, buffers per symbol
 └────────┬─────────┘
          │ Ticks buffered (rolling time window)
          ▼
 ┌──────────────────┐
 │  Signal Engine   │  (Python) Computes:
 │  (Phase 2)       │  • Context-aware VWAP deviation
 │                  │  • Rolling window statistics
 │                  │  • Feature normalization (z-scores)
 └────────┬─────────┘
          │ Normalized feature vectors per symbol
          ▼
 ┌──────────────────┐
 │  Scoring Engine  │  (Python) Time-based ranking:
 │  (Phase 2)       │  • Opening: Momentum priority
 │                  │  • Midday: VWAP deviation priority
 │                  │  • Normalized feature weighting
 └────────┬─────────┘
          │ Time-aware scores
          ▼
 ┌──────────────────┐
 │  Filters         │  (Python) Quality assurance:
 │  (Phase 2)       │  • Liquidity filter (spread + volume)
 │                  │  • Stability filter (persistent ranking)
 └────────┬─────────┘
          │ Filtered watchlist
          ▼
 ┌──────────────────┐
 │  Watchlist       │  (Python)
 │  Output          │  • Top 10 stable stocks every 3 seconds
 │  (Phase 2)       │  • Enhanced JSON with normalized signals
 └────────┬─────────┘
          │ Filtered watchlist
          ▼
 ┌──────────────────┐
 │  Strategy        │  (Python) Convert signals to BUY/SELL/HOLD
 │  Engine          │  decisions with deterministic rules
 │  (Phase 3)       │
 └────────┬─────────┘
          │ Trade signals
          ▼
 ┌──────────────────┐
 │  Risk Manager    │  (Python) Validate trades against limits
 │  (Phase 3)       │  • Position sizes, stop losses, daily loss
 └────────┬─────────┘
          │ Approved trades
          ▼
 ┌──────────────────┐
 │  Execution       │  (Python) Paper trading simulation
 │  Engine          │  • Update portfolio, no real broker
 │  (Phase 3)       │
 └────────┬─────────┘
          │ Portfolio updates
          ▼
 ┌──────────────────┐
 │  Portfolio       │  (Python) Track positions, cash, PnL
 │  Manager         │  • Real-time portfolio state
 │  (Phase 3)       │
 └────────┬─────────┘
          │
          ▼
 ┌──────────────────┐
 │  Trade Logger    │  (Python) Record all actions
 │  (Phase 3)       │  • CSV/JSON logs for analysis
 └──────────────────┘

```

### Component Responsibilities

| Component | Language | Responsibility |
|-----------|----------|-----------------|
| **Tick Simulator** | C++ | Generate realistic mock tick data with random walk price movements |
| **Ingestion Engine** | C++ | Parse, validate, deduplicate ticks; maintain latest state |
| **ZeroMQ Publisher** | C++ | Broadcast validated ticks to subscribers |
| **ZeroMQ Subscriber** | Python | Receive and buffer tick data per symbol (time-based windows) |
| **Signal Engine** | Python | Compute VWAP deviation, rolling stats, normalized features |
| **Scoring Engine** | Python | Time-based ranking with normalized feature weights |
| **Filters** | Python | Liquidity and stability filtering for quality |
| **Strategy Engine** | Python | Convert watchlist to BUY/SELL/HOLD decisions |
| **Risk Manager** | Python | Validate trades against position/stop loss limits |
| **Execution Engine** | Python | Simulate paper trading execution |
| **Portfolio Manager** | Python | Track positions, cash, PnL calculations |
| **Trade Logger** | Python | Record all trading actions to CSV/JSON |
| **Watchlist Output** | Python | Display and persist enhanced results |

---

## 🚀 Phase 2 Enhancements

Phase 2 introduces advanced signal intelligence while preserving the existing C++ ingestion pipeline and ZeroMQ communication.

### 1. Context-Aware Signals (VWAP Deviation)

**Problem:** Raw price signals are noisy and lack market context.

**Solution:** VWAP deviation = (current_price - intraday_VWAP) / intraday_VWAP

- **Positive deviation**: Stock is overvalued relative to intraday fair value
- **Negative deviation**: Stock is undervalued relative to intraday fair value
- **Computation**: Rolling VWAP using all ticks in 5-minute window
- **Benefit**: Trading signals based on intraday valuation rather than absolute price

### 2. Rolling Window Engine (Noise Reduction)

**Problem:** Fixed-size buffers don't account for time-based market behavior.

**Solution:** Time-based rolling windows (default: 5 minutes)

- **Automatic cleanup**: Old ticks beyond window are removed
- **Memory efficient**: No unbounded growth
- **Statistics**: Rolling mean, standard deviation for normalization
- **Benefit**: Signals reflect recent market context, not stale data

### 3. Feature Normalization (Fair Comparison)

**Problem:** Raw features have different scales, causing some to dominate scoring.

**Solution:** Z-score normalization: (value - rolling_mean) / rolling_std

- **Applied to**: momentum, volume_spike, VWAP_deviation
- **Benefit**: All features contribute equally, preventing scale bias
- **Example**: momentum z-score of 2.0 = 2 standard deviations above recent average

### 4. Time-Based Scoring (Market Awareness)

**Problem:** Market behavior changes throughout the day.

**Solution:** Dynamic weights based on market session:

- **Opening (9:30-10:30)**: Momentum priority [3,1,1,1] - Capture breakout moves
- **Midday (10:30-15:30)**: VWAP deviation priority [1,1,1,3] - Mean reversion opportunities  
- **Closing (15:30-16:00)**: Balanced [2,2,1,2] - Mixed signals

**Benefit**: Aligns with real intraday market dynamics.

### 5. Liquidity & Tradability Filter

**Problem:** Illiquid stocks create false signals and execution issues.

**Solution:** Pre-ranking filters:

- **Spread filter**: Spread ≤ 0.10 (configurable)
- **Volume filter**: Average volume ≥ 1000 (configurable)
- **Benefit**: Only tradable stocks enter the watchlist

### 6. Watchlist Stability Filter

**Problem:** Frequent watchlist churn reduces usability.

**Solution:** Persistence requirement:

- **Logic**: Stock must rank in top 15 for 3 consecutive cycles
- **Benefit**: Reduces noise, provides stable, actionable watchlist
- **Result**: Fewer but more reliable signals

### Configuration Examples

```python
# Phase 2 Configuration (python_engine/config.py)
ROLLING_WINDOW_SECONDS = 300        # 5-minute rolling window
NORMALIZATION_ENABLED = True         # Enable z-score normalization
STABILITY_CYCLES_REQUIRED = 3        # 3 cycles persistence
MAX_SPREAD_THRESHOLD = 0.10          # Max spread for liquidity
MIN_VOLUME_THRESHOLD = 1000          # Min volume for liquidity

# Time-based weights [momentum, volume_spike, spread_tight, vwap_dev]
SCORING_WEIGHTS_OPENING = [3, 1, 1, 1]   # Momentum focus
SCORING_WEIGHTS_MIDDAY = [1, 1, 1, 3]    # VWAP focus
SCORING_WEIGHTS_CLOSING = [2, 2, 1, 2]   # Balanced
```

### Performance Impact

- **Memory**: Stable usage with time-based cleanup
- **CPU**: Minimal overhead (~5-10% increase)
- **Latency**: No impact on real-time processing
- **Compatibility**: Fully backward compatible with Phase 1

### Example Phase 2 Output

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     🎯 PHASE 2 ENHANCED WATCHLIST 🎯                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Rank Symbol Score Reason             Momentum Vol.Spike VWAP.Dev Spread Price ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  1   AAPL   7.2  momentum+vwap_dev   0.003245  2.15     0.004512  0.015 $150.25 ║
║  2   MSFT   6.8  volume_spike        0.001845  3.42     0.002134  0.012 $320.50 ║
╚═══════════════════════════════════════════════════════════════════════════════╝
[STATUS] 100 symbols tracked, 85 passed filters, 2 stable stocks in watchlist
[TIMESTAMP] 2024-04-23T12:34:56.789012
```

**Key Improvements:**
- **Reason column**: Explains why stock is ranked (e.g., "momentum+vwap_dev")
- **Normalized signals**: Fair comparison across stocks
- **Stability**: Only persistent top performers shown
- **Quality**: Liquidity filters remove illiquid stocks

---

## 💰 Phase 3: Complete Trading System

Phase 3 transforms the watchlist generator into a fully functional trading system while maintaining the existing Phase 1-2 architecture.

### Trading Pipeline Architecture

```
Phase 2 Output (Watchlist) → Phase 3 Trading Pipeline
                                      │
                                      ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Strategy       │ -> │     Risk         │ -> │   Execution      │
│   Engine         │    │   Manager        │    │   Engine         │
│                  │    │                  │    │                  │
│ • BUY/SELL/HOLD  │    │ • Position limits │    │ • Paper trading │
│ • Deterministic  │    │ • Stop losses     │    │ • Portfolio      │
│ • Cooldown logic │    │ • Daily loss      │    │ • No slippage    │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                    ┌──────────────────┐    ┌──────────────────┐
                    │   Portfolio      │ -> │    Logger       │
                    │   Manager        │    │                 │
                    │                  │    │ • CSV/JSON logs │
                    │ • PnL tracking   │    │ • Trade records  │
                    │ • Position state │    │ • Debug info     │
                    └──────────────────┘    └──────────────────┘
```

### 1. Strategy Engine (`strategy.py`)

**Purpose:** Convert watchlist signals into actionable trade decisions.

**Logic:**
- **BUY**: Score ≥ 5.0 AND Momentum ≥ 0.001 AND No position AND Not on cooldown
- **SELL**: Score dropped OR Momentum reversed OR Stop loss triggered
- **HOLD**: Otherwise

**Features:**
- Deterministic rules (no ML/randomness)
- 60-second cooldown between trades per symbol
- Position-aware decisions

### 2. Risk Management (`risk_manager.py`)

**Purpose:** Validate trades before execution.

**Rules:**
- **Position Size**: Max 10% of portfolio per stock
- **Total Exposure**: Max 50% of portfolio across all positions
- **Stop Loss**: 5% loss triggers sell
- **Daily Loss Limit**: Stop trading if daily loss > 10%

**Authority:** Final approval required for all trades.

### 3. Execution Engine (`execution_engine.py`)

**Purpose:** Simulate paper trading execution.

**Features:**
- No real broker integration (Phase 3 = simulation only)
- Zero slippage for Phase 3
- Updates portfolio state immediately
- Handles BUY (open/increase) and SELL (reduce/close)

### 4. Portfolio Manager (`portfolio.py`)

**Purpose:** Track complete trading state.

**Tracks:**
- Cash balance ($100,000 starting)
- Positions per symbol (quantity, avg price)
- Realized and unrealized PnL
- Portfolio value calculations

### 5. Trade Logger (`logger.py`)

**Purpose:** Record all system actions.

**Outputs:**
- **CSV**: `trades.csv` - Trade execution data
- **JSON**: `trades.json` - Structured debug logs
- **Categories**: Signals, Decisions, Risk Checks, Executions, Errors

### 6. Backtesting Engine (`backtester.py`)

**Purpose:** Validate strategy on historical data.

**Features:**
- Replays tick data sequentially
- Same logic as live trading
- Comprehensive metrics: Win rate, Sharpe ratio, Max drawdown
- Memory-efficient processing

### Phase 3 Configuration

```python
# Phase 3 Trading Configuration (python_engine/config.py)
PAPER_MODE = True                    # Always simulation mode
INITIAL_CASH = 100000.0             # Starting capital
STRATEGY_SCORE_THRESHOLD = 5.0      # Min score for trading
RISK_MAX_POSITION_SIZE = 0.1        # 10% of portfolio per stock
RISK_STOP_LOSS_PERCENT = 0.05       # 5% stop loss
LOG_CSV_FILE = "trades.csv"         # Trade log
LOG_JSON_FILE = "trades.json"       # Debug log
```

### Example Phase 3 Output

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     🎯 PHASE 2 ENHANCED WATCHLIST 🎯                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Rank Symbol Score Reason             Momentum Vol.Spike VWAP.Dev Spread Price ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  1   AAPL   7.2  momentum+vwap_dev   0.003245  2.15     0.004512  0.015 $150.25 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

[TRADE] BUY 100 AAPL @ $150.25
[PORTFOLIO] Cash: $98,475.00 | Value: $100,025.00 | PnL: $25.00
[POSITIONS]
  AAPL: 100 @ $150.25 | Unrealized: $0.00
```

### Trading Lifecycle

1. **Signal Generation**: Phase 2 watchlist updated every 3 seconds
2. **Strategy**: Convert top signals to BUY/SELL decisions
3. **Risk Check**: Validate against position/stop loss limits
4. **Execution**: Update portfolio with paper trade
5. **Logging**: Record all actions for analysis
6. **Portfolio**: Display current state and PnL

### Backtesting

```bash
# Run backtest on historical data
cd python_engine
python3 -c "
from backtester import Backtester
from signal_engine import SignalEngine
from scoring import ScoringEngine
from strategy import StrategyEngine
from risk_manager import RiskManager
from execution_engine import ExecutionEngine
from portfolio import PortfolioManager
from logger import TradeLogger
import config

# Initialize components
signal_engine = SignalEngine(config)
scoring_engine = ScoringEngine(config)
portfolio = PortfolioManager(config.INITIAL_CASH)
logger = TradeLogger(config.LOG_CSV_FILE, config.LOG_JSON_FILE)
strategy = StrategyEngine(config)
risk = RiskManager(config, portfolio)
execution = ExecutionEngine(config, portfolio, risk)

# Create backtester
backtester = Backtester(config, signal_engine, scoring_engine, strategy, risk, execution, portfolio, logger)

# Load and run backtest
tick_data = backtester.load_tick_data_from_file('backtest_data.json')
results = backtester.run_backtest(tick_data)

print(f'Backtest Results:')
print(f'Total PnL: ${results[\"total_pnl\"]:.2f}')
print(f'Win Rate: {results[\"win_rate\"]:.1%}')
print(f'Max Drawdown: {results[\"max_drawdown\"]:.1%}')
print(f'Total Trades: {results[\"total_trades\"]}')
"

## 💻 System Requirements

### Local Development

**For C++ Build:**
- Ubuntu 24.04 LTS (or compatible Linux distro)
- CMake 3.10+
- C++17 compiler (g++, clang++)
- ZeroMQ development libraries (`libzmq3-dev`, `libcppzmq-dev`)
- Python 3.10+ (for running Python components)

**For Python Runtime:**
- Python 3.10+
- pip and venv
- ZeroMQ runtime (`libzmq3`)
- NumPy, Pandas, ZMQ bindings
- PyYAML (for Phase 4 configuration)
- KiteConnect (for Phase 4 live trading)

**Phase 4 Dependencies:**
```bash
pip install PyYAML==6.0 kiteconnect==4.10.0
```

**Minimal System Specs:**
- 2+ CPU cores
- 512 MB RAM
- Network connectivity (localhost for testing)

### Docker

- Docker 20.10+
- Docker Compose 2.0+
- 2+ GB disk space for images

---

## 🚀 Quick Start (Docker)

### Prerequisites

```bash
# Install Docker and Docker Compose
# Ubuntu/Debian:
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2

# Add user to docker group (optional, avoids sudo)
sudo usermod -aG docker $USER
newgrp docker
```

### Run Everything in Containers

```bash
cd /path/to/Hft-style-watchlist

# Build images and start services
docker compose -f docker/docker-compose.yml up --build

# Expected output:
# ingestion-engine  | [INGESTION] Starting tick simulator and publisher...
# signal-engine     | [PYTHON] Waiting for tick data...
# signal-engine     | [PYTHON] Processed 5000 ticks from 50 symbols
# signal-engine     | ╔═══════════════════════════════════════╗
# signal-engine     | ║        🎯 TOP WATCHLIST STOCKS 🎯    ║
# signal-engine     | ║ Rank  Symbol  Score   Momentum...   ║
# ...

# View output files
cat watchlist.json

# Graceful shutdown
docker compose -f docker/docker-compose.yml down
```

---

## 🔨 Build Instructions

### Local C++ Build

```bash
# Navigate to project root
cd /path/to/Hft-style-watchlist

# Install dependencies
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libzmq3-dev \
    libcppzmq-dev \
    pkg-config

# Build C++ ingestion engine
cd cpp_ingestion
mkdir -p build
cd build
cmake ..
cmake --build . --config Release
cd ../..

# Verify build
ls -la cpp_ingestion/build/ingestion_engine
# Should see: ingestion_engine executable
```

### Python Environment Setup

```bash
# Navigate to project root
cd /path/to/Hft-style-watchlist

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r python_engine/requirements.txt

# Verify installation
python3 -c "import zmq; print(f'ZMQ version: {zmq.__version__}')"
python3 -c "import numpy; print(f'NumPy version: {numpy.__version__}')"
```

---

## ⚙️ Configuration

### Phase 4 YAML Configuration (Recommended)

Phase 4 uses centralized YAML configuration for all settings. Create `python_engine/config.yaml`:

```yaml
# config.yaml - Phase 4 Production Configuration
trading:
  mode: "paper"                    # "paper", "paper_live_data", "live"
  live_trading_enabled: false      # MUST be true for live mode

  # Risk management parameters
  risk:
    max_position_pct: 0.10         # Max 10% of portfolio per position
    max_portfolio_exposure: 0.50   # Max 50% total exposure
    stop_loss_pct: 0.05            # 5% stop loss per position
    daily_loss_limit_pct: 0.10     # Max 10% daily loss

  # Execution settings
  execution:
    slippage_pct: 0.001            # 0.1% slippage for paper trades
    transaction_fee_pct: 0.0005    # 0.05% transaction fees
    min_order_value: 1000          # Minimum order value ($1000)
    max_order_value: 100000        # Maximum order value ($100k)

# Broker configuration (required for live trading)
broker:
  zerodha:
    api_key: "your_api_key_here"
    api_secret: "your_api_secret_here"
    request_token: "your_request_token_here"
    access_token: "your_access_token_here"
    user_id: "your_user_id_here"

# System settings
system:
  zmq_endpoint: "tcp://localhost:5555"
  refresh_interval_seconds: 3
  output_file: "watchlist.json"
  log_file: "trades.csv"

# Phase 2 signal processing (enhanced features)
signals:
  rolling_window_seconds: 300      # 5-minute time-based window
  normalization_enabled: true      # Enable z-score normalization
  max_spread_threshold: 0.10       # Maximum spread for tradable stocks
  min_volume_threshold: 1000       # Minimum average volume
  stability_cycles_required: 3     # Must be stable for N cycles
  stability_top_n: 15              # Consider top 15 for stability

  # Time-based scoring weights
  scoring_weights:
    opening: [3, 1, 1, 1]          # 9:30-10:30: Momentum focus
    midday: [1, 1, 1, 3]           # 10:30-15:30: VWAP focus
    closing: [2, 2, 1, 2]          # 15:30-16:00: Balanced

# Market session configuration
market:
  open_hour: 9
  open_minute: 30
  close_hour: 16
  close_minute: 0
  midday_start_hour: 10
  midday_start_minute: 30
```

**Configuration Validation:**
- Live trading requires `trading.live_trading_enabled: true`
- Broker credentials must be provided for live mode
- Risk parameters are validated at startup
- Invalid configurations prevent system startup

### Legacy Phase 1-3 Python Configuration

All configuration parameters can still be defined in `python_engine/config.py`. Key settings:

### Phase 1 (Core) Settings

```python
# ZeroMQ
ZMQ_ENDPOINT = "tcp://localhost:5555"

# Signal thresholds
MOMENTUM_THRESHOLD = 0.002           # Detect >0.2% price change
MOMENTUM_WINDOW = 20                 # Over last 20 ticks
VOLUME_SPIKE_THRESHOLD = 2.0         # Volume > 2x rolling average
VOLUME_MA_WINDOW = 20                # 20-tick moving average

# Output
WATCHLIST_SIZE = 10                  # Top 10 stocks
REFRESH_INTERVAL_SECONDS = 3         # Update every 3 seconds
OUTPUT_FILE = "watchlist.json"       # JSON output location

# Scoring weights (Phase 1)
SCORE_MOMENTUM_UP = 2                # Points for strong momentum
SCORE_VOLUME_SPIKE = 2               # Points for volume spike
SCORE_SPREAD_TIGHT = 1               # Points for tradable spread
SCORE_VWAP_DEV = 2                   # Points for VWAP deviation
```

### Phase 2 (Enhanced) Settings

```python
# Rolling Window (Phase 2)
ROLLING_WINDOW_SECONDS = 300         # 5-minute time-based window
NORMALIZATION_ENABLED = True         # Enable z-score normalization

# Liquidity Filters (Phase 2)
MAX_SPREAD_THRESHOLD = 0.10          # Maximum spread for tradable stocks
MIN_VOLUME_THRESHOLD = 1000          # Minimum average volume

# Time-Based Scoring (Phase 2)
# Weights: [momentum, volume_spike, spread_tight, vwap_dev]
SCORING_WEIGHTS_OPENING = [3, 1, 1, 1]   # 9:30-10:30: Momentum focus
SCORING_WEIGHTS_MIDDAY = [1, 1, 1, 3]    # 10:30-15:30: VWAP focus
SCORING_WEIGHTS_CLOSING = [2, 2, 1, 2]   # 15:30-16:00: Balanced

# Market Session Times
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0
MIDDAY_START_HOUR = 10
MIDDAY_START_MINUTE = 30

# Stability Filter (Phase 2)
STABILITY_CYCLES_REQUIRED = 3        # Must be in top N for X cycles
STABILITY_TOP_N = 15                 # Consider top 15 for stability check
```

**To tune the system:** Edit `python_engine/config.py` and restart the Python engine.

### Phase 2 Tuning Guide

**For More Aggressive Signals:**
```python
ROLLING_WINDOW_SECONDS = 180         # Shorter 3-minute window
STABILITY_CYCLES_REQUIRED = 2        # Faster stabilization
SCORING_WEIGHTS_MIDDAY = [1, 2, 1, 4]  # Increase VWAP weight
```

**For More Conservative Signals:**
```python
ROLLING_WINDOW_SECONDS = 600         # Longer 10-minute window
STABILITY_CYCLES_REQUIRED = 5        # Slower stabilization
MAX_SPREAD_THRESHOLD = 0.05          # Tighter liquidity filter
MIN_VOLUME_THRESHOLD = 2000          # Higher volume requirement
```

**For Different Market Sessions:**
```python
# Volatile market (increase momentum)
SCORING_WEIGHTS_OPENING = [4, 1, 1, 1]

# Sideways market (increase mean reversion)
SCORING_WEIGHTS_MIDDAY = [1, 1, 1, 4]
```

---

## 🏃 Running the System

### Phase 4 Quick Start (Recommended)

#### Safe Paper Trading (Default)

```bash
cd /workspaces/Hft-style-watchlist

# Terminal 1: Start C++ ingestion
cd cpp_ingestion/build
./ingestion_engine

# Terminal 2: Start Python trading system (safe paper mode)
cd python_engine
python3 main.py

# Expected output:
# ════════════════════════════════════════════════════════════════════════════════
#    HFT-Style Watchlist: Phase 4 Production Trading System
# ════════════════════════════════════════════════════════════════════════════════
# [PHASE 4] Execution Mode: PAPER (Safe)
# [PHASE 4] Risk Limits: Max Position 10.0%, Daily Loss 10.0%
# [PHASE 4] Initial Cash: $100,000.00
# [PHASE 4] YAML Config Loaded: config.yaml
# [PYTHON] Connecting to ZeroMQ at tcp://localhost:5555...
# [PYTHON] Phase 4 Features: YAML Config, Execution Factory, Safety Controls
# [PYTHON] Waiting for tick data...
```

#### Forward Testing (Real Data + Paper Execution)

```bash
# Edit config.yaml to enable forward testing
trading:
  mode: "paper_live_data"  # Real market data, paper execution
  live_trading_enabled: false  # Keep false for safety

# Run system
cd python_engine
python3 main.py

# Output shows real market data but paper trades
# [PHASE 4] Execution Mode: PAPER_LIVE_DATA (Forward Testing)
```

#### Live Trading (Production Mode)

**⚠️ WARNING: Live trading involves real money. Ensure all safety checks are met.**

For Upstox live trading, configure access_token as described in Phase 4 section.

```yaml
# config.yaml - Enable live trading
trading:
  mode: "live"
  live_trading_enabled: true  # REQUIRED for live mode

upstox:
  api_key: "your_api_key"
  access_token: "your_access_token"
  instruments: [...]
```

```bash
# Terminal 1: C++ ingestion
cd cpp_ingestion/build
DATA_SOURCE=upstox ./ingestion_engine

# Terminal 2: Upstox bridge
cd python_bridge
python3 main.py

# Terminal 3: Trading system
cd python_engine
python3 main.py
```

### Legacy Phase 1-3 Running Instructions

**Terminal 1: Start C++ Ingestion Engine**

```bash
cd /path/to/Hft-style-watchlist
cd cpp_ingestion/build

./ingestion_engine

# Expected output:
# === HFT-Style Watchlist: C++ Ingestion Engine ===
# [INGESTION] Starting tick simulator and publisher...
# [INGESTION] Waiting for subscriber connections (2 seconds)...
# [INGESTION] Publishing ticks at ~500/sec...
# [INGESTION] Published 5000 ticks (~497 ticks/sec)
```

**Terminal 2: Start Python Trading Engine (Phase 3)**

```bash
cd /path/to/Hft-style-watchlist
source venv/bin/activate

python3 python_engine/main.py

# Expected output:
# ════════════════════════════════════════════════════════════════════════════════
#    HFT-Style Watchlist: Phase 3 Enhanced Trading System
# ════════════════════════════════════════════════════════════════════════════════
# [PHASE 3] Paper Trading Mode: True
# [PHASE 3] Initial Cash: $100,000.00
# [PHASE 3] Risk Limits: Max Position 10.0%, Daily Loss 10.0%
# [PYTHON] Connecting to ZeroMQ at tcp://localhost:5555...
# [PYTHON] Phase 2 Features: Rolling Windows, Normalization, Time-Based Scoring
# [PYTHON] Waiting for tick data...
# ────────────────────────────────────────────────────────────────────────────────
# [PYTHON] Processed 5000 ticks from 50 symbols
# 
# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                     🎯 PHASE 2 ENHANCED WATCHLIST 🎯                        ║
# ╠═══════════════════════════════════════════════════════════════════════════════╣
# ║ Rank Symbol Score Reason             Momentum Vol.Spike VWAP.Dev Spread Price ║
# ╠═══════════════════════════════════════════════════════════════════════════════╣
# ║  1   AAPL   7.2  momentum+vwap_dev   0.003245  2.15     0.004512  0.015 $150.25 ║
# ║  2   MSFT   6.8  volume_spike        0.001845  3.42     0.002134  0.012 $320.50 ║
# ...
# ╚═══════════════════════════════════════════════════════════════════════════════╝
# [TRADE] BUY 100 AAPL @ $150.25
# [PORTFOLIO] Cash: $98,475.00 | Value: $100,025.00 | PnL: $25.00
# [POSITIONS]
#   AAPL: 100 @ $150.25 | Unrealized: $0.00
# [STATUS] 100 symbols tracked, 85 passed filters, 2 stable stocks in watchlist
# [TIMESTAMP] 2024-04-23T12:34:56.789012
```

**Phase 3 Features:**
- **Watchlist**: Phase 2 enhanced signals with stability filtering
- **Trading**: Automatic BUY/SELL decisions based on strategy rules
- **Portfolio**: Real-time position and PnL tracking
- **Risk**: Stop losses, position limits, daily loss limits
- **Logging**: All actions recorded to `trades.csv` and `trades.json`

**Graceful Shutdown**

Press `Ctrl+C` in either terminal to cleanly shutdown that component.

### Option 2: Docker Compose

```bash
cd /path/to/Hft-style-watchlist

# Start all services
docker compose -f docker/docker-compose.yml up

# View logs
docker compose -f docker/docker-compose.yml logs -f

# Shutdown
docker compose -f docker/docker-compose.yml down
```

### Option 3: systemd Services (Production)

```bash
# Create service file for ingestion engine
sudo tee /etc/systemd/system/hft-ingestion.service > /dev/null <<EOF
[Unit]
Description=HFT Ingestion Engine
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/path/to/Hft-style-watchlist/cpp_ingestion/build
ExecStart=/path/to/Hft-style-watchlist/cpp_ingestion/build/ingestion_engine
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create service file for signal engine
sudo tee /etc/systemd/system/hft-signal.service > /dev/null <<EOF
[Unit]
Description=HFT Signal Engine
After=hft-ingestion.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/path/to/Hft-style-watchlist
ExecStart=/path/to/Hft-style-watchlist/venv/bin/python /path/to/Hft-style-watchlist/python_engine/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable hft-ingestion hft-signal
sudo systemctl start hft-ingestion hft-signal
sudo systemctl status hft-ingestion hft-signal
```

---

## 📊 Output Format

### Phase 2 Console Output (Real-time)

The enhanced watchlist is printed to console every 3 seconds with stability filtering:

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     🎯 PHASE 2 ENHANCED WATCHLIST 🎯                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Rank Symbol Score Reason             Momentum Vol.Spike VWAP.Dev Spread Price ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  1   AAPL   7.2  momentum+vwap_dev   0.003245  2.15     0.004512  0.015 $150.25 ║
║  2   MSFT   6.8  volume_spike        0.001845  3.42     0.002134  0.012 $320.50 ║
║  3   GOOG   6.3  momentum            0.002845  1.85     0.001234  0.014 $140.75 ║
╚═══════════════════════════════════════════════════════════════════════════════╝
[STATUS] 100 symbols tracked, 85 passed filters, 3 stable stocks in watchlist
[TIMESTAMP] 2024-04-23T12:34:56.789012
```

**Phase 2 Enhancements:**
- **Reason column**: Explains ranking factors (e.g., "momentum+vwap_dev")
- **Stability filtering**: Only shows stocks that have been consistently ranked
- **Liquidity filtering**: Removes illiquid stocks before ranking
- **Time-based scoring**: Weights adjust based on market session

### Phase 2 JSON Output (watchlist.json)

File location: `./watchlist.json` (or `/app/output/watchlist.json` in Docker)

```json
{
  "timestamp": "2024-04-23T12:34:56.789012",
  "total_symbols_tracked": 100,
  "total_symbols_filtered": 85,
  "total_ticks_processed": 45000,
  "watchlist": [
    {
      "rank": 1,
      "symbol": "AAPL",
      "score": 7.2,
      "reason": "momentum+vwap_dev",
      "signals": {
        "momentum": 0.003245,
        "volume_spike": 2.15,
        "vwap": 150.2480,
        "vwap_deviation": 0.004512,
        "spread": 0.0150,
        "current_price": 150.25,
        "bid": 150.24,
        "ask": 150.26,
        "momentum_normalized": 1.85,
        "volume_spike_normalized": 2.12,
        "vwap_deviation_normalized": 1.67
      }
    }
  ]
}
```

**Field Descriptions:**

- **rank**: Position in the stable watchlist (1 = highest score)
- **symbol**: Stock ticker
- **score**: Time-based composite score using normalized features
- **reason**: Explanation of ranking factors (e.g., "momentum+vwap_dev")
- **Raw signals**: Original computed values
  - **momentum**: Price change over momentum window
  - **volume_spike**: Current volume / rolling average ratio
  - **vwap**: Volume-weighted average price (intraday)
  - **vwap_deviation**: Deviation from VWAP (context signal)
  - **spread**: Bid-ask spread (liquidity)
  - **current_price**: Last traded price
- **Normalized signals** (Phase 2): Z-score normalized features
  - **momentum_normalized**: (momentum - rolling_mean) / rolling_std
  - **volume_spike_normalized**: (volume_spike - rolling_mean) / rolling_std
  - **vwap_deviation_normalized**: (vwap_dev - rolling_mean) / rolling_std

### Backward Compatibility

Phase 2 maintains full compatibility with Phase 1:
- Same JSON structure (adds optional normalized fields)
- Same ZeroMQ protocol
- Same C++ ingestion engine
- Can disable Phase 2 features by setting `NORMALIZATION_ENABLED = False`

---

## 🧪 Simulation Details

### Tick Generator Behavior

The C++ tick simulator generates 100 realistic stock symbols with:

**Price Movement (Random Walk):**
```
new_price = current_price * (1 + random_drift)
where:
  random_drift ~ Normal(mean=0, sigma=0.001)
```

This creates realistic price series similar to actual market behavior.

**Volume Generation:**
```
volume ~ Uniform(100, 10,000) ticks
with 5% chance of volume spike: volume *= 5
```

**Bid-Ask Spread:**
```
spread ~ Uniform(0.01, 0.10)
bid = price - spread/2
ask = price + spread/2
```

### Symbols Simulated

100 real stock tickers: AAPL, MSFT, GOOGL, AMZN, TSLA, BRK.B, JNJ, V, WMT, PG, MA, HD, NFLX, DIS, BA, IBM, INTC, AMD, COIN, NVDA, CRM, ADBE, ACN, CSCO, ORCL, QCOM, TXN, AVGO, NXPI, MU, PYPL, SQ, TTD, NET, CRWD, OKTA, ZS, SNPS, CDNS, MCHP, ASML, AMAT, LRCX, KLA, ONTO, MRVL, MSTR, RIOT, MARA, CLSK, GOOG, FB, TWTR, SNAP, PIN, PINS, SHOP, ETSY, FTCH, DASH, UBER, LYFT, RBLX, U, PTON, ZILLOW, ABNB, LCID, RIVN, NIO, XPev, LI, BIDU, PDD, SE, DDOG, SNOW, ZM, MDB, DBX, BOX, NEWR, LMND, HUBS, S, FSLY, SUMO, REGI, TREX, PLYA, KMTB, EXLS, VRSN, JKHY, JBHT, CHRW, XPO, J, UTL, YUM

---

## 📖 Detailed Data Flow

### 1. Tick Generation (C++)

```
TickSimulator::generate_tick()
  → Random walk price movement
  → Random volume (with spike chance)
  → Random bid/ask spread
  → Returns: struct Tick { symbol, price, volume, bid, ask, timestamp }
```

### 2. Data Ingestion (C++)

```
IngestionEngine (main.cpp)
  → For each generated tick:
    1. Store in unordered_map (O(1) latest tick per symbol)
    2. Validate timestamp (non-stale)
    3. Check for duplicates
    4. Serialize to binary format
    5. Publish via ZeroMQ
```

### 3. Network Transport (ZeroMQ)

```
ZMQ PUB/SUB Pattern:
  C++ Publisher (port 5555) → Broadcast all ticks
  Python Subscriber → Receive and deserialize
  
  Message Format (binary):
  [symbol_len(1b)|symbol(N b)|price(8b)|volume(8b)|bid(8b)|ask(8b)|timestamp(8b)]
  
  Performance:
  ~500 ticks/sec
  ~2-3ms latency per hop
  Negligible CPU overhead
```

### 4. Signal Computation (Python)

For each new tick, periodically compute (every 3 seconds or on watchlist refresh):

```
For each symbol in buffer:
  1. compute_momentum()
     → Recent price change detection
  2. compute_volume_spike()
     → Unusual trading activity
  3. compute_vwap()
     → Fair value estimation
  4. compute_spread()
     → Liquidity indicator
```

### 5. Scoring & Ranking (Python)

```
For each symbol's signals:
  score = 0
  if momentum > 0.002:          score += 2
  if volume_spike > 2.0:        score += 2
  if spread < 0.05:             score += 1
  if abs(vwap_dev) > 0.02:      score += 2
  
Sort all symbols by score (descending)
Select top 10
```

### 6. Output (Python)

```
Every 3 seconds:
  1. Print formatted table to console
  2. Write JSON to watchlist.json
  3. Log statistics
```

---

## � Phase 4: Production Trading System

Phase 4 introduces **production-grade execution capabilities** with dual execution modes (paper and live trading), strict safety controls to prevent accidental real trades, centralized configuration management via YAML, and forward testing capabilities.

### Key Phase 4 Features

- **🛡️ Dual Execution Modes**: Paper trading (default safe mode) and live trading (explicitly enabled)
- **🔒 Safety First**: Multiple layers of protection prevent accidental real trades
- **⚙️ YAML Configuration**: Centralized, validated configuration with environment-specific settings
- **📊 Forward Testing**: Real market data with paper execution for strategy validation
- **🏭 Execution Factory**: Centralized mode selection with runtime safety checks
- **🔄 Live Integration**: Zerodha Kite API integration with retry logic and validation
- **📈 Enhanced Risk Management**: YAML-configurable position limits, stop losses, and exposure controls

### Phase 4 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HFT-Style Watchlist                               │
│                            Phase 4 Architecture                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │   C++       │    │   Python    │    │   Python    │    │   Python    │   │
│  │ Ingestion   │───▶│   Signal    │───▶│   Strategy  │───▶│   Risk      │   │
│  │ Engine      │    │ Processing  │    │   Engine    │    │   Manager   │   │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘   │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │   Python    │    │   Python    │    │   Execution │                      │
│  │   Portfolio │───▶│   Logger    │───▶│   Factory   │                      │
│  │   Manager   │    │   System    │    │             │                      │
│  └─────────────┘    └─────────────┘    │             │                      │
│                                        │             │                      │
│                                        ├─────────────┤                      │
│                                        │ Paper Exec. │                      │
│                                        │ (Default)   │                      │
│                                        ├─────────────┤                      │
│                                        │ Live Exec.  │                      │
│                                        │ (Zerodha)   │                      │
│                                        └─────────────┘                      │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │   YAML      │    │   Config    │    │   System    │    │   Safety    │   │
│  │   Config    │───▶│   Loader    │───▶│   Runner    │───▶│   Controls  │   │
│  │   File      │    │   (Valid.)  │    │   (Entry)   │    │   (Multi)   │   │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Phase 4 Components:**
- **Execution Factory**: Centralized mode selection with safety validation
- **Paper Execution**: Safe simulation with slippage and portfolio updates
- **Live Execution**: Real trading via Zerodha Kite API with validation and retries
- **YAML Config**: Structured configuration with validation rules
- **System Runner**: Entry point that loads config and initializes components
- **Safety Controls**: Multiple layers preventing accidental live trades

### Execution Modes

#### 🧾 Paper Trading Mode (Default)
- **Purpose**: Safe strategy testing and development
- **Behavior**: Simulates trades with realistic slippage and fees
- **Safety**: No external API calls, no real money at risk
- **Use Case**: Strategy development, backtesting, forward testing

#### 📈 Live Trading Mode
- **Purpose**: Production trading with real money
- **Behavior**: Executes real orders via Zerodha Kite API
- **Safety**: Requires explicit enablement, multiple validation checks
- **Use Case**: Production deployment with real market exposure

#### 🔄 Forward Testing Mode
- **Purpose**: Strategy validation with real-time market data
- **Behavior**: Uses live market data but executes paper trades
- **Safety**: Real data, simulated execution, no financial risk
- **Use Case**: Pre-production validation, performance monitoring

### Safety Controls

Phase 4 implements **multiple layers of safety** to prevent accidental real trades:

1. **Configuration Validation**
   - Live trading requires explicit `trading.live_trading_enabled: true`
   - Invalid configurations are rejected at startup
   - Broker credentials validated before live mode activation

2. **Runtime Safety Checks**
   - Execution factory validates mode selection
   - Live execution requires valid broker session
   - Position limits and risk checks enforced

3. **Operational Safeguards**
   - Paper mode is default (safe by design)
   - Live mode requires manual configuration changes
   - Clear logging distinguishes paper vs live executions

### YAML Configuration

Phase 4 uses centralized YAML configuration for all settings:

```yaml
# config.yaml
trading:
  mode: "paper"  # "paper", "paper_live_data", "live"
  live_trading_enabled: false  # MUST be true for live mode

  # Risk parameters
  risk:
    max_position_pct: 0.10      # Max 10% of portfolio per position
    max_portfolio_exposure: 0.50 # Max 50% total exposure
    stop_loss_pct: 0.05         # 5% stop loss per position
    daily_loss_limit_pct: 0.10  # Max 10% daily loss

  # Execution settings
  execution:
    slippage_pct: 0.001         # 0.1% slippage for paper trades
    transaction_fee_pct: 0.0005 # 0.05% fees
    min_order_value: 1000       # Minimum order value
    max_order_value: 100000     # Maximum order value

# Broker configuration (for live trading)
broker:
  zerodha:
    api_key: "your_api_key"
    api_secret: "your_api_secret"
    request_token: "your_request_token"
    access_token: "your_access_token"
    user_id: "your_user_id"

# System settings
system:
  zmq_endpoint: "tcp://localhost:5555"
  refresh_interval_seconds: 3
  output_file: "watchlist.json"
  log_file: "trades.csv"
```

**Configuration Validation Rules:**
- `trading.live_trading_enabled` must be `true` for live mode
- Broker credentials required for live mode
- Risk parameters must be within safe bounds
- Invalid configurations prevent system startup

### Running Phase 4 System

#### Quick Start (Paper Trading - Safe Default)

```bash
cd /workspaces/Hft-style-watchlist

# Start C++ ingestion (Terminal 1)
cd cpp_ingestion/build
./ingestion_engine

# Start Python trading system (Terminal 2)
cd python_engine
python3 main.py

# Expected output:
# ════════════════════════════════════════════════════════════════════════════════
#    HFT-Style Watchlist: Phase 4 Production Trading System
# ════════════════════════════════════════════════════════════════════════════════
# [PHASE 4] Execution Mode: PAPER (Safe)
# [PHASE 4] Risk Limits: Max Position 10.0%, Daily Loss 10.0%
# [PHASE 4] Initial Cash: $100,000.00
# [PYTHON] Connecting to ZeroMQ at tcp://localhost:5555...
# [PYTHON] Phase 4 Features: YAML Config, Execution Factory, Safety Controls
# [PYTHON] Waiting for tick data...
```

#### Forward Testing (Real Data + Paper Execution)

```bash
# Edit config.yaml
trading:
  mode: "paper_live_data"
  live_trading_enabled: false  # Keep false for safety

# Run system
cd python_engine
python3 main.py
```

#### Live Trading (Production - Requires Setup)

**Step 1: Configure Broker Credentials**

```yaml
# config.yaml
trading:
  mode: "live"
  live_trading_enabled: true  # EXPLICITLY ENABLE

broker:
  zerodha:
    api_key: "your_api_key"
    api_secret: "your_api_secret"
    # ... other credentials
```

**Step 2: Generate Access Token**

```bash
# Use Kite login URL to get request token
# Then generate access token
cd python_engine
python3 -c "
from kiteconnect import KiteConnect
kite = KiteConnect(api_key='your_api_key')
print('Login URL:', kite.login_url())
# Follow URL, get request_token, then:
# kite.generate_session(request_token, api_secret)
"
```

**Step 3: Run Live System**

```bash
cd python_engine
python3 main.py

# Expected output:
# [PHASE 4] Execution Mode: LIVE (Production)
# [PHASE 4] Broker: Zerodha Kite API Connected
# [WARNING] LIVE TRADING ENABLED - REAL MONEY AT RISK
```

### Phase 4 Output Format

#### Enhanced Console Output

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     🎯 PHASE 4 PRODUCTION WATCHLIST 🎯                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ Rank Symbol Score Reason             Momentum Vol.Spike VWAP.Dev Spread Price ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  1   AAPL   7.2  momentum+vwap_dev   0.003245  2.15     0.004512  0.015 $150.25 ║
║  2   MSFT   6.8  volume_spike        0.001845  3.42     0.002134  0.012 $320.50 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

[TRADE] BUY 100 AAPL @ $150.25 (PAPER) - Slippage: $0.15
[PORTFOLIO] Cash: $98,474.85 | Value: $100,025.15 | PnL: $25.15
[POSITIONS] AAPL: 100 @ $150.25 | Unrealized: $0.00
[EXECUTION] Mode: PAPER | Result: SUCCESS
[STATUS] 100 symbols tracked, 85 passed filters, 2 stable stocks in watchlist
[TIMESTAMP] 2024-04-23T12:34:56.789012
```

**Phase 4 Enhancements:**
- **Mode Indicator**: Shows execution mode (PAPER/LIVE) in trade logs
- **Slippage Tracking**: Shows simulated/real slippage applied
- **Result Status**: SUCCESS/FAILED/REJECTED for each execution
- **Safety Confirmation**: Clear indication of paper vs live execution

#### Enhanced CSV Logging

```csv
timestamp,symbol,action,quantity,price,mode,result,slippage,fees,pnl_realized,portfolio_value
2024-04-23T12:34:56.789012,AAPL,BUY,100,150.25,PAPER,SUCCESS,0.15,0.75,0.00,100025.15
2024-04-23T12:35:00.123456,MSFT,SELL,50,320.50,PAPER,SUCCESS,0.16,0.80,125.00,100150.15
```

**New Fields:**
- **mode**: PAPER or LIVE
- **result**: SUCCESS, FAILED, REJECTED
- **slippage**: Applied slippage amount
- **fees**: Transaction fees charged

#### Enhanced JSON Logging

```json
{
  "timestamp": "2024-04-23T12:34:56.789012",
  "execution": {
    "mode": "PAPER",
    "result": "SUCCESS",
    "symbol": "AAPL",
    "action": "BUY",
    "quantity": 100,
    "price": 150.25,
    "slippage": 0.15,
    "fees": 0.75
  },
  "portfolio": {
    "cash": 98474.85,
    "total_value": 100025.15,
    "unrealized_pnl": 0.00,
    "realized_pnl": 25.15
  },
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "avg_price": 150.25,
      "current_price": 150.25,
      "unrealized_pnl": 0.00
    }
  ]
}
```

### Phase 4 Dependencies

Add to `requirements.txt`:

```txt
PyYAML==6.0
kiteconnect==4.10.0
```

**Installation:**
```bash
pip install PyYAML==6.0 kiteconnect==4.10.0
```

### Phase 4 Safety Checklist

**Before Live Trading:**
- [ ] `trading.live_trading_enabled: true` in config.yaml
- [ ] Valid Zerodha API credentials configured
- [ ] Access token generated and valid
- [ ] Risk limits set appropriately for account size
- [ ] Test in paper mode first
- [ ] Forward test with real data
- [ ] Monitor initial live trades manually

**Runtime Safety:**
- [ ] System logs show "LIVE (Production)" mode
- [ ] Trade confirmations show real prices and quantities
- [ ] Portfolio updates reflect actual broker positions
- [ ] Stop losses trigger correctly
- [ ] Daily loss limits enforced

---

## �🐛 Troubleshooting

### C++ Build Errors

**Error:** `fatal error: zmq.hpp: No such file or directory`

```bash
# Solution: Install CMake header
sudo apt-get install libcppzmq-dev
```

**Error:** `undefined reference to zmq_*`

```bash
# Solution: Install ZMQ library
sudo apt-get install libzmq3-dev
```

**Error:** `CMake not found`

```bash
# Solution: Install CMake
sudo apt-get install cmake
```

### Python Runtime Errors

**Error:** `ModuleNotFoundError: No module named 'zmq'`

```bash
# Solution: Install Python dependencies
source venv/bin/activate
pip install zmq
```

**Error:** `ConnectionRefusedError: [Errno 111] Connection refused`

```bash
# Solution: Ensure C++ ingestion engine is running
# Terminal 1: Start C++ and wait 2 seconds
./cpp_ingestion/build/ingestion_engine

# Terminal 2: Start Python (after 2-second delay)
python3 python_engine/main.py
```

**Error:** `watchlist.json` not created

```bash
# Solution: Check Python output permissions
chmod 755 /path/to/project/python_engine

# Verify JSON file is being written
tail -f watchlist.json
```

### Performance Issues

**Issue:** Slow tick rate or missed ticks

```
Check:
1. CPU usage: top -p $(pgrep -f ingestion_engine)
2. ZMQ queue depth: Monitor via ZMQ stats
3. Python CPU: top -p $(pgrep -f main.py)
4. Disk I/O: watchlist.json writes

Solution:
- Reduce REFRESH_INTERVAL_SECONDS in config.py
- Increase MAX_BUFFER_SIZE if symbols are heavily lagging
- Check system load: uptime
```

**Issue:** Memory leaks

```bash
# Monitor memory over time
watch -n 1 'ps aux | grep -E "(ingestion_engine|main.py)" | grep -v grep'

# Use valgrind (C++)
valgrind --leak-check=full ./cpp_ingestion/build/ingestion_engine
```

### Connection Issues

**Issue:** "Address already in use"

```bash
# Kill existing processes
pkill -f ingestion_engine
pkill -f "python.*main.py"

# Or: Find and kill specific port
lsof -i :5555
kill -9 <PID>
```

---

## 📂 Project Structure

```
Hft-style-watchlist/
│
├── README.md                          # This file
│
├── cpp_ingestion/                     # C++ Ingestion Layer (Unchanged)
│   ├── main.cpp                       # Entry point (orchestrates pipeline)
│   ├── tick_simulator.cpp             # Market tick generator
│   ├── zmq_publisher.cpp              # ZeroMQ broadcast
│   ├── CMakeLists.txt                 # Build configuration
│   └── build/                         # Build artifacts (after cmake)
│       └── ingestion_engine           # Compiled binary
│
├── python_engine/                     # Python Processing Layer (Phase 2 + Phase 3 + Phase 4)
│   ├── main.py                        # Orchestrator (ZMQ sub, signal compute, trading pipeline)
│   ├── signal_engine.py               # Feature calculations (momentum, VWAP, etc.)
│   ├── scoring.py                     # Ranking logic with time-based weights
│   ├── config.py                      # Legacy config (Phase 1-3)
│   ├── config.yaml                    # Phase 4: YAML configuration (recommended)
│   ├── requirements.txt               # Python dependencies (includes Phase 4)
│   ├── watchlist.json                 # Output file (generated)
│   │
│   ├── strategy.py                    # Phase 3: Trade decision logic
│   ├── risk_manager.py                # Phase 3: Risk validation (enhanced for Phase 4)
│   ├── execution_engine.py            # Phase 3: Legacy execution (replaced by Phase 4)
│   ├── portfolio.py                   # Phase 3: Portfolio state management
│   ├── logger.py                      # Phase 3: Action logging (enhanced for Phase 4)
│   ├── backtester.py                  # Phase 3: Historical simulation
│   │
│   ├── execution/                     # Phase 4: Execution Layer
│   │   ├── __init__.py                # Package initialization
│   │   ├── base_execution.py          # Abstract execution interface
│   │   ├── paper_execution.py         # Safe paper trading simulation
│   │   ├── live_execution.py          # Live trading via Zerodha Kite API
│   │   ├── execution_factory.py       # Centralized mode selection & safety
│   │   ├── config/                    # Configuration management
│   │   │   ├── __init__.py            # Config package
│   │   │   ├── config_loader.py       # YAML loader with validation
│   │   │   └── config.yaml            # Default configuration template
│   │   └── core/                      # System integration
│   │       ├── __init__.py            # Core package
│   │       └── system_runner.py       # Phase 4 entry point
│   │
│   ├── trades.csv                     # Trade execution log (enhanced for Phase 4)
│   └── trades.json                    # Structured debug logs (enhanced for Phase 4)
│
├── shared/                            # Shared Definitions
│   └── schema.json                    # Tick data format specification
│
├── docker/                            # Containerization
│   ├── Dockerfile.cpp                 # C++ build & runtime image
│   ├── Dockerfile.python              # Python runtime image
│   └── docker-compose.yml             # Multi-container orchestration
│
└── (venv/)                            # Python virtual environment (created locally)
```

### File Responsibilities

| File | Responsibility |
|------|-----------------|
| `main.cpp` | Wires simulator, ingestion, and publisher together |
| `tick_simulator.cpp` | Generates realistic market data with random walk |
| `zmq_publisher.cpp` | Publishes serialized ticks via ZeroMQ |
| `main.py` | Subscribes to ZMQ, orchestrates signal/scoring/trading pipeline |
| `signal_engine.py` | Buffers ticks, computes momentum/VWAP/volume/spread |
| `scoring.py` | Time-based ranking with normalized features |
| `strategy.py` | Converts watchlist to BUY/SELL/HOLD decisions |
| `risk_manager.py` | Validates trades against position/stop loss limits (enhanced for Phase 4) |
| `execution_engine.py` | Legacy Phase 3 execution (replaced by Phase 4 execution package) |
| `portfolio.py` | Tracks positions, cash, PnL calculations |
| `logger.py` | Records all actions to CSV/JSON logs (enhanced for Phase 4) |
| `backtester.py` | Runs historical simulations with same logic |
| `config.py` | Legacy configuration (Phase 1-3) |
| `config.yaml` | Phase 4 YAML configuration (recommended) |
| `execution/base_execution.py` | Phase 4: Abstract execution interface |
| `execution/paper_execution.py` | Phase 4: Safe paper trading with slippage |
| `execution/live_execution.py` | Phase 4: Live trading via Zerodha Kite API |
| `execution/execution_factory.py` | Phase 4: Mode selection with safety validation |
| `execution/config/config_loader.py` | Phase 4: YAML config loader with validation |
| `execution/core/system_runner.py` | Phase 4: Production system entry point |
| `schema.json` | Documents tick binary format |
| `CMakeLists.txt` | C++ build instructions |

---

## ⚡ Performance Notes

### Latency Breakdown

```
Path: Tick Generation → Publication → Subscription → Signal Computation

1. Tick Generation:   < 0.1 ms (C++ memory operation)
2. Ingestion/Valid:   < 0.1 ms (O(1) map lookup, validation)
3. ZMQ Publish:       1-2 ms (network write to subscriber)
4. Python Receive:    < 0.1 ms (socket read)
5. Deserialization:   < 0.1 ms (struct unpacking)
6. Buffer Append:     < 0.1 ms (deque append)
7. Signal Compute:    ~5-10 ms per watchlist (600ms interval → ~1% CPU)

Total End-to-End: ~7-13 ms per tick (acceptable for non-HFT systems)
```

### Throughput

- **Ingestion Rate:** ~500 ticks/sec (configurable via sleep interval)
- **Symbols Handled:** 100 concurrent symbols without degradation
- **Watchlist Refresh:** Every 3 seconds (configurable)
- **Memory Footprint:**
  - C++: ~50 MB (latest tick per symbol)
  - Python: ~200 MB (rolling buffers + logic)
  - Total: ~250 MB

### Optimization Tips

1. **Reduce buffer size** if memory is constrained:
   ```python
   MAX_BUFFER_SIZE = 100  # Default: 500
   ```

2. **Increase watchlist refresh interval** to reduce CPU:
   ```python
   REFRESH_INTERVAL_SECONDS = 5  # Default: 3
   ```

3. **Compile C++ with optimizations** (already done in CMakeLists.txt with `-O3`)

4. **Use binary serialization** (already implemented) instead of JSON for ticks

---

## 🚀 Next Steps / Future Enhancements

While this is a complete Phase 1 system, here are ideas for future development:

1. **Real Market Data Integration**
   - Replace tick simulator with live API (Alpha Vantage, Alpaca, IB)
   - Add authentication and rate limiting

2. **ML-Based Scoring**
   - Train LSTM on historical data to predict price movement
   - Ensemble scoring with multiple models

3. **Risk Management**
   - Position sizing based on volatility
   - Dynamic stop-loss logic

4. **Execution Layer**
   - Paper trading simulation
   - Live order execution (with careful risk controls)

5. **Dashboard**
   - Real-time web UI (React + WebSocket)
   - Historical watchlist tracking

6. **Backtesting Framework**
   - Replay historical data
   - Performance metrics and optimization

---

## � Phase 4: Upstox WebSocket Market Data Integration

Phase 4 upgrades the system to consume real-time market data from Upstox via WebSocket, replacing simulated data with live feeds.

### WebSocket Integration Architecture

```
Upstox API → OAuth Auth → WebSocket Auth → Protobuf Stream → Decode → Normalize → ZeroMQ → Existing Pipeline
```

### Key Components

1. **Token Management (`token_manager.py`)**: Handles access tokens with expiry detection
2. **WebSocket Auth (`ws_auth_client.py`)**: Fetches authorized WSS URL from Upstox
3. **WebSocket Client (`websocket_client.py`)**: Async connection with reconnection logic
4. **Subscription Manager (`subscription_manager.py`)**: Manages instrument subscriptions
5. **Protobuf Decoder (`proto_decoder.py`)**: Decodes binary messages using official Upstox schema
6. **Data Normalizer (`data_normalizer.py`)**: Converts to internal format

### OAuth Authentication

**Where:** Handled in `python_bridge/auth.py` and `token_manager.py`

**How it works:**
- Loads `access_token` from config (`config.yaml`) or environment (`UPSTOX_ACCESS_TOKEN`)
- For live data, obtain access token from Upstox developer portal
- Set in config or export as env var

**How to login:**
1. Go to [Upstox Developer Portal](https://upstox.com/developer/)
2. Create app and get API key/secret
3. Use OAuth flow to get access token
4. Set `UPSTOX_ACCESS_TOKEN` in environment or config

**Example:**
```bash
export UPSTOX_ACCESS_TOKEN="your_access_token_here"
```

### Running with Live Data

```bash
# Terminal 1: C++ ingestion (external mode)
cd cpp_ingestion/build
DATA_SOURCE=upstox ./ingestion_engine

# Terminal 2: Upstox bridge
cd python_bridge
python3 main.py

# Terminal 3: Signal engine
cd python_engine
python3 main.py
```

### Configuration for Phase 4

```yaml
upstox:
  api_key: "YOUR_API_KEY"
  access_token: "YOUR_ACCESS_TOKEN"
  instruments:
    - "NSE_EQ|RELIANCE"
    - "NSE_EQ|TCS"
  mode: "full"

websocket:
  reconnect_backoff_sec: 2
  max_backoff_sec: 30
```

### Error Handling

- **Token Expiry**: Auto-invalidates and retries with new token
- **Connection Loss**: Exponential backoff reconnection
- **Decode Failures**: Logs and continues processing
- **Subscription Errors**: Resubscribes on reconnect

---

## �📝 License & Attribution

This project is provided as an educational resource for learning real-time trading systems architecture. Use at your own risk.

---

## 📞 Support

For issues, questions, or improvements:

1. Check the **Troubleshooting** section above
2. Review **config.py** for tuning options
3. Enable **ENABLE_DEBUG_LOGGING = True** in config.py for verbose output
4. Check system resources: `top`, `free`, `df`

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] C++ ingestion engine compiles without errors
- [ ] Python dependencies install successfully
- [ ] ZeroMQ endpoint (localhost:5555) is accessible
- [ ] First watchlist prints within 10 seconds of starting Python
- [ ] watchlist.json file is created and updated every 3 seconds
- [ ] Top 10 stocks display with non-zero scores
- [ ] System operates for >5 minutes without errors
- [ ] Graceful shutdown works (Ctrl+C)

---

**Happy Trading! 📈**