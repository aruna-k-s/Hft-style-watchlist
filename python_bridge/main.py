#!/usr/bin/env python3

import signal
import sys
from websocket_client import WebSocketClient

def main():
    client = WebSocketClient()

    def shutdown(signum, frame):
        print('[WS_CLIENT] Shutdown signal received')
        client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        client.run()
    except KeyboardInterrupt:
        client.stop()

if __name__ == '__main__':
    main()