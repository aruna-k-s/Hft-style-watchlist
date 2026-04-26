import asyncio
import os
import sys
import time
import logging
import zmq
import struct
from typing import Optional

import websockets

# Ensure python_engine package is importable
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PYTHON_ENGINE_DIR = os.path.join(ROOT_DIR, 'python_engine')
if PYTHON_ENGINE_DIR not in sys.path:
    sys.path.insert(0, PYTHON_ENGINE_DIR)

from execution.config.config_loader import load_trading_config
from token_manager import TokenManager
from ws_auth_client import get_authorized_url
from subscription_manager import subscribe, resubscribe
from proto_decoder import decode
from data_normalizer import normalize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketClient:
    DEFAULT_ZMQ_ENDPOINT = os.getenv('UPSTOX_BRIDGE_ENDPOINT', 'tcp://*:5556')
    DEFAULT_RECONNECT_BACKOFF_SEC = 2
    DEFAULT_MAX_BACKOFF_SEC = 30

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(ROOT_DIR, 'python_engine', 'execution', 'config', 'config.yaml')
        self.config = load_trading_config(self.config_path)
        self.token_manager = TokenManager(self.config_path)
        self.zmq_endpoint = os.getenv('UPSTOX_BRIDGE_ZMQ_ENDPOINT', self.DEFAULT_ZMQ_ENDPOINT)

        self.zmq_context = zmq.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.PUB)
        self.zmq_socket.bind(self.zmq_endpoint)

        self.instruments = self.config.upstox.instruments
        self.backoff = self.DEFAULT_RECONNECT_BACKOFF_SEC
        self.max_backoff = self.DEFAULT_MAX_BACKOFF_SEC

        logger.info(f"[WS_CLIENT] Starting WebSocket client on {self.zmq_endpoint}")
        logger.info(f"[WS_CLIENT] Instruments: {self.instruments}")

    def handle_error(self, e):
        if "401" in str(e) or "Unauthorized" in str(e):
            self.token_manager.invalidate_token()
            logger.warning("[WS_CLIENT] Token invalidated due to auth error")
        else:
            logger.error(f"[WS_CLIENT] Error: {e}")

    async def connect_loop(self):
        while True:
            token = self.token_manager.get_token()
            if not token:
                logger.error("[WS_CLIENT] No valid token available")
                await asyncio.sleep(self.backoff)
                continue

            try:
                wss_url = get_authorized_url(token)
                logger.info(f"[WS_CLIENT] Connecting to {wss_url}")

                async with websockets.connect(wss_url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("[WS_CLIENT] Connected")
                    await subscribe(ws, self.instruments)
                    logger.info("[WS_CLIENT] Subscribed")

                    async for message in ws:
                        decoded_feeds = decode(message)
                        if decoded_feeds:
                            for instrument_key, feed_data in decoded_feeds.items():
                                normalized = normalize(feed_data)
                                if normalized:
                                    self._publish_tick(normalized)
                        else:
                            logger.warning("[WS_CLIENT] Failed to decode message")

            except Exception as e:
                self.handle_error(e)
                await asyncio.sleep(self.backoff)
                self.backoff = min(self.backoff * 2, self.max_backoff)

    def _publish_tick(self, tick: dict):
        symbol = tick['symbol']
        price = float(tick['price'])
        volume = int(tick['volume'])
        bid = float(tick['bid'])
        ask = float(tick['ask'])
        timestamp = int(tick['timestamp'])

        if len(symbol) > 255:
            symbol = symbol[:255]

        message = bytearray()
        message.append(len(symbol))
        message.extend(symbol.encode('utf-8'))
        message.extend(struct.pack('d', price))
        message.extend(struct.pack('Q', volume))
        message.extend(struct.pack('d', bid))
        message.extend(struct.pack('d', ask))
        message.extend(struct.pack('Q', timestamp))

        self.zmq_socket.send(message)
        logger.info(f"[WS_CLIENT] Published tick {symbol} price={price} volume={volume}")

    def run(self):
        asyncio.run(self.connect_loop())

    def stop(self):
        self.zmq_socket.close()
        self.zmq_context.term()