#!/bin/bash
# Verification Script for HFT-Style Watchlist Generator
# Run this after setup to verify everything is working

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ $1${NC}"
        ((FAILED++))
    fi
}

echo "═════════════════════════════════════════════════════════════"
echo "       HFT-Style Watchlist Generator - Verification"
echo "═════════════════════════════════════════════════════════════"
echo ""

# Check C++ Build
echo -e "${YELLOW}Checking C++ Build...${NC}"
[ -f "$PROJECT_ROOT/cpp_ingestion/build/ingestion_engine" ]
check "C++ binary exists"

[ -x "$PROJECT_ROOT/cpp_ingestion/build/ingestion_engine" ]
check "C++ binary is executable"

# Check Python Environment
echo -e "${YELLOW}Checking Python Environment...${NC}"
[ -d "$PROJECT_ROOT/venv" ]
check "Virtual environment exists"

# Source venv
source "$PROJECT_ROOT/venv/bin/activate" 2>/dev/null || true

# Check Python packages
python3 -c "import zmq" 2>/dev/null
check "Python ZMQ module installed"

python3 -c "import numpy" 2>/dev/null
check "Python NumPy module installed"

python3 -c "import pandas" 2>/dev/null
check "Python Pandas module installed"

# Check File Structure
echo -e "${YELLOW}Checking Project Structure...${NC}"
[ -f "$PROJECT_ROOT/README.md" ]
check "README.md exists"

[ -f "$PROJECT_ROOT/IMPLEMENTATION.md" ]
check "IMPLEMENTATION.md exists"

[ -f "$PROJECT_ROOT/cpp_ingestion/main.cpp" ]
check "C++ main.cpp exists"

[ -f "$PROJECT_ROOT/python_engine/main.py" ]
check "Python main.py exists"

[ -f "$PROJECT_ROOT/python_engine/signal_engine.py" ]
check "Python signal_engine.py exists"

[ -f "$PROJECT_ROOT/python_engine/scoring.py" ]
check "Python scoring.py exists"

[ -f "$PROJECT_ROOT/python_engine/config.py" ]
check "Python config.py exists"

[ -f "$PROJECT_ROOT/shared/schema.json" ]
check "Shared schema.json exists"

[ -f "$PROJECT_ROOT/docker/Dockerfile.cpp" ]
check "Dockerfile.cpp exists"

[ -f "$PROJECT_ROOT/docker/Dockerfile.python" ]
check "Dockerfile.python exists"

[ -f "$PROJECT_ROOT/docker/docker-compose.yml" ]
check "docker-compose.yml exists"

# Check Configuration
echo -e "${YELLOW}Checking Python Configuration...${NC}"
grep -q "ZMQ_ENDPOINT" "$PROJECT_ROOT/python_engine/config.py"
check "ZMQ_ENDPOINT configured"

grep -q "MOMENTUM_THRESHOLD" "$PROJECT_ROOT/python_engine/config.py"
check "MOMENTUM_THRESHOLD configured"

grep -q "WATCHLIST_SIZE" "$PROJECT_ROOT/python_engine/config.py"
check "WATCHLIST_SIZE configured"

# Check Schema
echo -e "${YELLOW}Checking Schema Definition...${NC}"
grep -q "\"symbol\":" "$PROJECT_ROOT/shared/schema.json"
check "Schema defines symbol field"

grep -q "\"price\":" "$PROJECT_ROOT/shared/schema.json"
check "Schema defines price field"

grep -q "\"volume\":" "$PROJECT_ROOT/shared/schema.json"
check "Schema defines volume field"

# System availability
echo -e "${YELLOW}Checking System Resources...${NC}"
which cmake >/dev/null 2>&1
check "CMake is installed"

which python3 >/dev/null 2>&1
check "Python3 is installed"

which g++ >/dev/null 2>&1 || which clang++ >/dev/null 2>&1
check "C++ compiler is installed"

# Summary
echo ""
echo "═════════════════════════════════════════════════════════════"
echo -e "Results: ${GREEN}$PASSED PASSED${NC}, ${RED}$FAILED FAILED${NC}"
echo "═════════════════════════════════════════════════════════════"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All checks passed! System is ready to run.${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Start the C++ ingestion engine:"
    echo "   cd $PROJECT_ROOT/cpp_ingestion/build"
    echo "   ./ingestion_engine"
    echo ""
    echo "2. In another terminal, start the Python engine:"
    echo "   cd $PROJECT_ROOT"
    echo "   source venv/bin/activate"
    echo "   python3 python_engine/main.py"
    echo ""
    exit 0
else
    echo -e "${RED}Some checks failed. Please review errors above.${NC}"
    exit 1
fi
