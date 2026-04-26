"""ZeroMQ publisher that emits tick frames in the existing binary schema."""

from __future__ import annotations

import logging
import struct
from typing import Mapping

import zmq


LOGGER = logging.getLogger(__name__)


class ZmqTickPublisher:
    """
    Publish ticks in the exact binary layout already consumed by python_engine/main.py:
    symbol_len(1) | symbol | price(8) | volume(8) | bid(8) | ask(8) | timestamp(8)
    """

    def __init__(self, bind_endpoint: str = "tcp://*:5555") -> None:
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.PUB)
        self._socket.bind(bind_endpoint)
        self._bind_endpoint = bind_endpoint
        self._published = 0

    @property
    def bind_endpoint(self) -> str:
        return self._bind_endpoint

    @property
    def published_count(self) -> int:
        return self._published

    def publish(self, tick: Mapping[str, object]) -> bool:
        try:
            message = self._serialize_tick(tick)
        except ValueError as exc:
            LOGGER.warning("bridge.publish.skip_invalid_tick error=%s tick=%s", exc, tick)
            return False

        self._socket.send(message)
        self._published += 1
        return True

    def close(self) -> None:
        try:
            self._socket.close(0)
        except Exception:  # pragma: no cover - best effort cleanup
            pass

    def _serialize_tick(self, tick: Mapping[str, object]) -> bytes:
        symbol_raw = tick.get("symbol")
        if not isinstance(symbol_raw, str) or not symbol_raw:
            raise ValueError("missing or invalid symbol")
        symbol_bytes = symbol_raw.encode("utf-8")
        if len(symbol_bytes) > 255:
            raise ValueError("symbol length exceeds 255 bytes")

        price = float(tick["price"])
        if price <= 0:
            raise ValueError("price must be > 0")

        volume_raw = int(tick["volume"])
        if volume_raw < 0:
            raise ValueError("volume must be >= 0")
        if volume_raw > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("volume exceeds uint64")

        timestamp_ns = self._normalize_to_ns(int(tick["timestamp"]))

        bid = float(tick.get("bid", price))
        ask = float(tick.get("ask", price))
        if bid > ask:
            bid, ask = ask, bid

        payload = bytearray()
        payload.append(len(symbol_bytes))
        payload.extend(symbol_bytes)
        payload.extend(struct.pack("d", price))
        payload.extend(struct.pack("Q", volume_raw))
        payload.extend(struct.pack("d", bid))
        payload.extend(struct.pack("d", ask))
        payload.extend(struct.pack("Q", timestamp_ns))
        return bytes(payload)

    @staticmethod
    def _normalize_to_ns(raw_ts: int) -> int:
        """
        Normalize exchange timestamps to nanoseconds.
        Heuristic:
        - <= 1e13  : milliseconds epoch  -> *1e6
        - <= 1e16  : microseconds epoch   -> *1e3
        - otherwise: assume nanoseconds already
        """
        if raw_ts <= 0:
            raise ValueError("timestamp must be > 0")
        if raw_ts <= 10_000_000_000_000:
            return raw_ts * 1_000_000
        if raw_ts <= 10_000_000_000_000_000:
            return raw_ts * 1_000
        return raw_ts
