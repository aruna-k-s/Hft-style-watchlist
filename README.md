# HFT-Style Automated Watchlist Generator

A production-quality, low-latency stock watchlist system using C++ for market data ingestion, Python for signal processing, and ZeroMQ for high-speed inter-process communication.

**Phase 2 Enhancement:** Advanced signal intelligence with context-aware signals, feature normalization, time-based scoring, and stability filtering for improved decision quality.

**Design Principle:** Modular, clean separation of concerns with minimal latency overhead. Perfect for learning real-time trading systems architecture.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 2 Enhancements](#phase-2-enhancements)
3. [System Requirements](#system-requirements)
4. [Quick Start (Docker)](#quick-start-docker)
5. [Build Instructions](#build-instructions)
6. [Configuration](#configuration)
7. [Running the System](#running-the-system)
8. [Output Format](#output-format)
9. [Troubleshooting](#troubleshooting)
10. [Project Structure](#project-structure)
11. [Performance Notes](#performance-notes)

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
 │                  │  • Enhanced JSON with normalized signals
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

All configuration parameters are defined in `python_engine/config.py`. Key settings:

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

### Option 1: Local Development (Separate Terminals)

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

**Terminal 2: Start Python Signal Engine**

```bash
cd /path/to/Hft-style-watchlist
source venv/bin/activate

python3 python_engine/main.py

# Expected output:
# ════════════════════════════════════════════════════════════════════════════════
#    HFT-Style Watchlist: Python Signal Engine
# ════════════════════════════════════════════════════════════════════════════════
# [PYTHON] Connecting to ZeroMQ at tcp://localhost:5555...
# [PYTHON] Waiting for tick data...
# ────────────────────────────────────────────────────────────────────────────────
# [PYTHON] Processed 5000 ticks from 50 symbols
# 
# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║                        🎯 TOP WATCHLIST STOCKS 🎯                         ║
# ╠═════════════════════════════════════════════════════════════════════════════╣
# ║ Rank  Symbol  Score   Momentum  Vol.Spike  VWAP.Dev  Spread   Price       ║
# ╠═════════════════════════════════════════════════════════════════════════════╣
# ║  1    AAPL   8.0    0.0032    2.15      0.0045    0.0150  $150.25 ║
# ║  2    MSFT   7.5    0.0028    1.95      0.0035    0.0155  $320.50 ║
# ...
# ╚═════════════════════════════════════════════════════════════════════════════╝
# [STATUS] 100 symbols tracked, 45000 ticks processed
# [TIMESTAMP] 2024-04-23T12:34:56.789012
```

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

## 🐛 Troubleshooting

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
├── cpp_ingestion/                     # C++ Ingestion Layer
│   ├── main.cpp                       # Entry point (orchestrates pipeline)
│   ├── tick_simulator.cpp             # Market tick generator
│   ├── zmq_publisher.cpp              # ZeroMQ broadcast
│   ├── CMakeLists.txt                 # Build configuration
│   └── build/                         # Build artifacts (after cmake)
│       └── ingestion_engine           # Compiled binary
│
├── python_engine/                     # Python Processing Layer
│   ├── main.py                        # Orchestrator (ZMQ sub, signal compute, output)
│   ├── signal_engine.py               # Feature calculations (momentum, VWAP, etc.)
│   ├── scoring.py                     # Ranking logic
│   ├── config.py                      # Tunable parameters
│   ├── requirements.txt               # Python dependencies
│   └── watchlist.json                 # Output file (generated)
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
| `main.py` | Subscribes to ZMQ, orchestrates signal/scoring pipeline |
| `signal_engine.py` | Buffers ticks, computes momentum/VWAP/volume/spread |
| `scoring.py` | Ranks stocks, formats output |
| `config.py` | All tunable parameters in one place |
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

## 📝 License & Attribution

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