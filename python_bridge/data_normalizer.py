def normalize(data: dict) -> dict:
    if not data:
        return None

    price = float(data["price"])
    return {
        "symbol": data["symbol"],
        "price": price,
        "volume": int(data["volume"]),
        "bid": price * 0.999,
        "ask": price * 1.001,
        "timestamp": int(data["timestamp"])
    }