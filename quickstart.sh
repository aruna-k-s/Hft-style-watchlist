#!/bin/bash
# QUICKSTART - HFT-Style Watchlist Generator
# This script automates the setup and build process

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "========================================="
echo "HFT-Style Watchlist Generator - Quick Start"
echo "========================================="
echo "Project root: $PROJECT_ROOT"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Install system dependencies
echo -e "${YELLOW}[1/5] Installing system dependencies...${NC}"
sudo apt-get update > /dev/null
sudo apt-get install -y \
    build-essential \
    cmake \
    libzmq3-dev \
    libcppzmq-dev \
    pkg-config > /dev/null 2>&1
echo -e "${GREEN}✓ System dependencies installed${NC}"

# Step 2: Build C++ ingestion engine
echo -e "${YELLOW}[2/5] Building C++ ingestion engine...${NC}"
cd "$PROJECT_ROOT/cpp_ingestion"
rm -rf build
mkdir -p build
cd build
cmake .. > /dev/null
cmake --build . --config Release > /dev/null 2>&1
cd "$PROJECT_ROOT"
echo -e "${GREEN}✓ C++ ingestion engine built${NC}"

# Step 3: Setup Python virtual environment
echo -e "${YELLOW}[3/5] Setting up Python virtual environment...${NC}"
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    python3 -m venv "$PROJECT_ROOT/venv" > /dev/null
fi
source "$PROJECT_ROOT/venv/bin/activate"
pip install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✓ Virtual environment created${NC}"

# Step 4: Install Python dependencies
echo -e "${YELLOW}[4/5] Installing Python dependencies...${NC}"
pip install -r "$PROJECT_ROOT/python_engine/requirements.txt" > /dev/null 2>&1
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Step 5: Verify builds
echo -e "${YELLOW}[5/5] Verifying builds...${NC}"
if [ -f "$PROJECT_ROOT/cpp_ingestion/build/ingestion_engine" ]; then
    echo -e "${GREEN}✓ C++ binary verified${NC}"
else
    echo "ERROR: C++ binary not found"
    exit 1
fi

python3 -c "import zmq; print('ZMQ OK')" > /dev/null 2>&1 && echo -e "${GREEN}✓ Python dependencies verified${NC}" || exit 1

echo ""
echo "========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo "To run the system:"
echo ""
echo "Terminal 1 (Ingestion Engine):"
echo "  cd $PROJECT_ROOT/cpp_ingestion/build"
echo "  ./ingestion_engine"
echo ""
echo "Terminal 2 (Signal Engine):"
echo "  source $PROJECT_ROOT/venv/bin/activate"
echo "  cd $PROJECT_ROOT"
echo "  python3 python_engine/main.py"
echo ""
echo "To use Docker Compose:"
echo "  cd $PROJECT_ROOT"
echo "  docker compose -f docker/docker-compose.yml up --build"
echo ""
echo "For detailed documentation, see README.md"
echo "========================================="
