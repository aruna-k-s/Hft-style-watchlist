"""Protobuf decoder for Upstox Market Data Feed V3 binary WebSocket messages."""

from __future__ import annotations

from typing import Dict, List, Optional

from google.protobuf.message import DecodeError

import marketdata_pb2


class ProtobufSchemaError(RuntimeError):
    """Raised when generated protobuf classes do not match expected Upstox schema."""


def _validate_schema() -> None:
    required_messages = ("FeedResponse", "Feed", "FullFeed", "LTPC")
    for message_name in required_messages:
        if not hasattr(marketdata_pb2, message_name):
            raise ProtobufSchemaError(
                f"Unsupported protobuf module: missing message '{message_name}'. "
                "Regenerate marketdata_pb2.py from official Upstox V3 marketdata.proto."
            )

    feed_fields = marketdata_pb2.Feed.DESCRIPTOR.fields_by_name
    if "ltpc" not in feed_fields or "fullFeed" not in feed_fields or "firstLevelWithGreeks" not in feed_fields:
        raise ProtobufSchemaError(
            "Unsupported Feed schema: expected oneof fields ltpc/fullFeed/firstLevelWithGreeks."
        )

    full_feed_fields = marketdata_pb2.FullFeed.DESCRIPTOR.fields_by_name
    if "marketFF" not in full_feed_fields or "indexFF" not in full_feed_fields:
        raise ProtobufSchemaError(
            "Unsupported FullFeed schema: expected oneof fields marketFF/indexFF."
        )


_validate_schema()


def _extract_ltpc(feed: marketdata_pb2.Feed) -> Optional[marketdata_pb2.LTPC]:
    feed_union = feed.WhichOneof("FeedUnion")
    if feed_union == "ltpc":
        return feed.ltpc

    if feed_union == "fullFeed":
        full_union = feed.fullFeed.WhichOneof("FullFeedUnion")
        if full_union == "marketFF":
            return feed.fullFeed.marketFF.ltpc
        if full_union == "indexFF":
            return feed.fullFeed.indexFF.ltpc
        return None

    if feed_union == "firstLevelWithGreeks":
        return feed.firstLevelWithGreeks.ltpc

    return None


def decode_many(message_bytes: bytes) -> List[Dict[str, object]]:
    """
    Decode one WebSocket binary frame into zero or more minimal ticks.

    Output schema is intentionally minimal and stable:
    {"symbol", "price", "volume", "timestamp"}
    """
    if not message_bytes:
        return []

    msg = marketdata_pb2.FeedResponse()
    try:
        msg.ParseFromString(message_bytes)
    except DecodeError:
        return []

    decoded_ticks: List[Dict[str, object]] = []
    for instrument_key, feed in msg.feeds.items():
        ltpc = _extract_ltpc(feed)
        if ltpc is None:
            continue

        if not instrument_key:
            continue

        decoded_ticks.append(
            {
                "symbol": instrument_key,
                "price": float(ltpc.ltp),
                "volume": int(ltpc.ltq),
                "timestamp": int(ltpc.ltt),
            }
        )

    return decoded_ticks


def decode(message_bytes: bytes) -> Optional[Dict[str, object]]:
    """
    Decode a WebSocket binary frame into a single minimal tick.

    Returns the first decodable tick when a frame contains multiple feeds.
    """
    decoded_ticks = decode_many(message_bytes)
    if not decoded_ticks:
        return None
    return decoded_ticks[0]
