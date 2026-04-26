import json
import os
import sys
import time
import signal
import struct
import threading
from typing import Any, Dict, List, Optional

import zmq
from websocket import WebSocketApp

# Ensure python_engine package is importable when running from python_bridge directory
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PYTHON_ENGINE_DIR = os.path.join(ROOT_DIR, 'python_engine')
if PYTHON_ENGINE_DIR not in sys.path:
    sys.path.insert(0, PYTHON_ENGINE_DIR)

from execution.config.config_loader import load_trading_config
from auth import load_upstox_tokens, reload_tokens_if_expired


class UpstoxBridge:
    """Lightweight bridge from Upstox websocket to ZeroMQ."""

    DEFAULT_ZMQ_ENDPOINT = os.getenv('UPSTOX_BRIDGE_ENDPOINT', 'tcp://*:5556')
    DEFAULT_RECONNECT_BASE = 1.0
    DEFAULT_RECONNECT_MAX = 60.0

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(ROOT_DIR, 'python_engine', 'execution', 'config', 'config.yaml')
        self.config = load_trading_config(self.config_path)
        self.tokens = load_upstox_tokens(self.config_path)
        self.provider = self.tokens['provider']
        self.zmq_endpoint = os.getenv('UPSTOX_BRIDGE_ZMQ_ENDPOINT', self.DEFAULT_ZMQ_ENDPOINT)

        self.websocket_url = getattr(self.config, 'upstox_websocket_url', 'wss://api.upstox.com/livefeed')
        self.instruments = self._load_instruments()
        self.running = False
        self.ws_app: Optional[WebSocketApp] = None
        self.zmq_context = zmq.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.PUB)
        self.zmq_socket.bind(self.zmq_endpoint)
        self._stop_event = threading.Event()

        print(f"[BRIDGE] Starting Upstox bridge on {self.zmq_endpoint}")
        print(f"[BRIDGE] Data source provider: {self.provider}")
        print(f"[BRIDGE] Subscribing to: {self.instruments}")

    def _load_instruments(self) -> List[str]:
        upstox_cfg = getattr(self.config, 'upstox', None)
        if upstox_cfg and getattr(upstox_cfg, 'instruments', None):
            return upstox_cfg.instruments
        return []

    def _build_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f"Bearer {self.tokens['access_token']}",
            'x-api-key': self.tokens['api_key'],
            'Content-Type': 'application/json'
        }

    def _on_open(self, ws: WebSocketApp) -> None:
        print('[BRIDGE] WebSocket connection opened')
        self._subscribe_instruments(ws)

    def _on_message(self, ws: WebSocketApp, message: str) -> None:
        try:
            payload = json.loads(message)
            tick = self._parse_tick(payload)
            if tick:
                self._publish_tick(tick)
        except json.JSONDecodeError:
            print('[BRIDGE] Received non-JSON message, ignoring')
        except Exception as exc:
            print(f'[BRIDGE] Error parsing message: {exc}')

    def _on_error(self, ws: WebSocketApp, error: Any) -> None:
        print(f'[BRIDGE] WebSocket error: {error}')

    def _on_close(self, ws: WebSocketApp, close_status_code: int, close_msg: str) -> None:
        print(f'[BRIDGE] WebSocket closed: code={close_status_code}, msg={close_msg}')

    def _subscribe_instruments(self, ws: WebSocketApp) -> None:
        if not self.instruments:
            print('[BRIDGE] No instruments configured for Upstox subscription')
            return

        # Upstox subscription format may vary; send a generic subscribe message
        payload = {
            'action': 'subscribe',
            'instruments': self.instruments,
        }
        ws.send(json.dumps(payload))
        print('[BRIDGE] Subscription request sent')

    def _parse_tick(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        symbol = payload.get('symbol') or payload.get('tradingsymbol') or payload.get('instrument')
        price = payload.get('last_price') or payload.get('price')
        volume = payload.get('volume') or payload.get('quantity') or payload.get('last_traded_qty')
        bid = payload.get('best_bid_price') or payload.get('bid')
        ask = payload.get('best_ask_price') or payload.get('ask')
        timestamp = payload.get('timestamp') or payload.get('time') or payload.get('last_trade_time')

        if symbol is None or price is None or volume is None:
            return None

        if bid is None or ask is None:
            bid = float(price) * 0.999
            ask = float(price) * 1.001

        if float(bid) >= float(ask):
            ask = float(bid) + 0.01

        if isinstance(timestamp, str):
            try:
                timestamp = int(float(timestamp) * 1000)
            except Exception:
                timestamp = int(time.time() * 1000)
        else:
            timestamp = int(timestamp)

        return {
            'symbol': symbol,
            'price': float(price),
            'volume': int(volume),
            'bid': float(bid),
            'ask': float(ask),
            'timestamp': int(timestamp)
        }

    def _publish_tick(self, tick: Dict[str, Any]) -> None:
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
        print(f"[BRIDGE] Published tick {symbol} price={price} volume={volume} mode=upstox result=filled")

    def _build_ws_url(self) -> str:
        return self.websocket_url

    def run(self) -> None:
        self.running = True
        retries = 0
        headers = self._build_headers()

        while self.running and not self._stop_event.is_set():
            try:
                self.ws_app = WebSocketApp(
                    self._build_ws_url(),
                    header=[f"{key}: {value}" for key, value in headers.items()],
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws_app.run_forever(ping_interval=20, ping_timeout=10)

            except Exception as exc:
                print(f'[BRIDGE] Connection error: {exc}')
                self.tokens = reload_tokens_if_expired(self.tokens)
                headers = self._build_headers()

            if self._stop_event.is_set():
                break

            retries += 1
            delay = min(self.DEFAULT_RECONNECT_BASE * (2 ** retries), self.DEFAULT_RECONNECT_MAX)
            print(f'[BRIDGE] Reconnecting in {delay:.1f} seconds...')
            time.sleep(delay)

    def stop(self) -> None:
        self.running = False
        self._stop_event.set()
        if self.ws_app is not None:
            self.ws_app.close()
        self.zmq_socket.close()
        self.zmq_context.term()


def main() -> None:
    bridge = UpstoxBridge()
    def shutdown(signum, frame):
        print('[BRIDGE] Shutdown signal received')
        bridge.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    bridge.run()


if __name__ == '__main__':
    main()
