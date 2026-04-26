"""Stateful Upstox WebSocket subscription management."""

from __future__ import annotations

import json
import uuid
from typing import Iterable, List


class SubscriptionManager:
    """Stores instrument state and manages subscribe/resubscribe lifecycle."""

    def __init__(self, instruments: Iterable[str], mode: str = "full", batch_size: int = 100) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")

        self.mode = mode
        self.batch_size = batch_size
        self.instruments: List[str] = self._normalize_instruments(instruments)

    @staticmethod
    def _normalize_instruments(instruments: Iterable[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for instrument in instruments:
            if not instrument:
                continue
            if instrument in seen:
                continue
            seen.add(instrument)
            normalized.append(instrument)
        return normalized

    def set_instruments(self, instruments: Iterable[str]) -> None:
        self.instruments = self._normalize_instruments(instruments)

    def add_instruments(self, instruments: Iterable[str]) -> None:
        merged = list(self.instruments)
        merged.extend(instruments)
        self.instruments = self._normalize_instruments(merged)

    def _batched_instruments(self) -> List[List[str]]:
        return [
            self.instruments[index : index + self.batch_size]
            for index in range(0, len(self.instruments), self.batch_size)
        ]

    async def subscribe(self, ws) -> None:
        if not self.instruments:
            raise ValueError("No instruments configured for subscription.")

        for instrument_batch in self._batched_instruments():
            payload = {
                "guid": str(uuid.uuid4()),
                "method": "sub",
                "data": {
                    "mode": self.mode,
                    "instrumentKeys": instrument_batch,
                },
            }
            await ws.send(json.dumps(payload).encode("utf-8"))

    async def resubscribe(self, ws) -> None:
        await self.subscribe(ws)
