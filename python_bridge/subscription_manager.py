import json
import uuid

async def subscribe(ws, instruments):
    payload = {
        "guid": str(uuid.uuid4()),
        "method": "sub",
        "data": {
            "mode": "full",
            "instrumentKeys": instruments
        }
    }

    await ws.send(json.dumps(payload))

async def resubscribe(ws, instruments):
    await subscribe(ws, instruments)