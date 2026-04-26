from google.protobuf.message import DecodeError
import MarketDataFeed_pb2 as marketdata_pb2

def decode(message_bytes: bytes) -> dict:
    try:
        msg = marketdata_pb2.FeedResponse()
        msg.ParseFromString(message_bytes)

        # Extract fields safely
        feeds = {}
        for instrument_key, feed in msg.feeds.items():
            if feed.HasField('ltpc'):
                feeds[instrument_key] = {
                    "symbol": instrument_key,
                    "price": feed.ltpc.ltp,
                    "volume": feed.ltpc.ltq,
                    "timestamp": feed.ltpc.ltt
                }

        return feeds

    except DecodeError:
        return None