# C++ Ingestion Module

This module provides high-performance market data ingestion using C++ and ZeroMQ.

## Files

- `main.cpp`: Entry point
- `tick_simulator.cpp`: Simulated market data generator
- `zmq_publisher.cpp`: ZeroMQ publisher
- `tick.h`: Data structures
- `CMakeLists.txt`: Build configuration

## Build

```bash
cd cpp_ingestion
mkdir build
cd build
cmake ..
make
```

## Usage

```bash
./ingestion_engine  # Simulated data
DATA_SOURCE=upstox ./ingestion_engine  # External data mode
```

## Phase

- **Phase 1**: Implemented