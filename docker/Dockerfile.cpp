# Build stage for C++ ingestion engine
FROM ubuntu:24.04 as builder

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libzmq3-dev \
    libcppzmq-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/cpp_ingestion

# Copy source code
COPY cpp_ingestion/ .

# Build
RUN mkdir -p build && cd build && \
    cmake .. && \
    cmake --build . --config Release

# Runtime stage
FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    libzmq3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the built binary from builder
COPY --from=builder /app/cpp_ingestion/build/ingestion_engine /app/

# Expose ZeroMQ port
EXPOSE 5555

# Run the ingestion engine
CMD ["./ingestion_engine"]
