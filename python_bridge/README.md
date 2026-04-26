# Python Bridge Module

This module handles the connection between external data sources (like Upstox) and the internal ZeroMQ pipeline.

## Files

- `auth.py`: Token loading and management
- `upstox_bridge.py`: Legacy JSON WebSocket bridge (deprecated)
- `token_manager.py`: OAuth token management
- `ws_auth_client.py`: WebSocket authorization client
- `websocket_client.py`: Async WebSocket client for Upstox
- `subscription_manager.py`: Instrument subscription management
- `proto_decoder.py`: Protobuf message decoding
- `data_normalizer.py`: Data format normalization
- `main.py`: Entry point for the bridge

## Usage

```bash
cd python_bridge
python3 main.py
```

## Configuration

See main README for Upstox configuration.

## OAuth

Tokens are loaded from config or environment. For login, obtain access_token from Upstox portal and set UPSTOX_ACCESS_TOKEN.