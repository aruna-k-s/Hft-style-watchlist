"""Runnable Upstox -> ZeroMQ bridge entrypoint."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from bridge_config import BridgeConfig, BridgeConfigError
from subscription_manager import SubscriptionManager
from token_manager import EnvTokenManager
from websocket_client import connect_loop
from zmq_tick_publisher import ZmqTickPublisher


LOGGER = logging.getLogger(__name__)


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def _run_bridge(config: BridgeConfig) -> None:
    token_manager = EnvTokenManager(
        initial_access_token=config.access_token,
        token_file=config.token_file,
        refresh_command=config.token_refresh_cmd,
        client_id=config.client_id,
        client_secret=config.client_secret,
        redirect_uri=config.redirect_uri,
        auth_code=config.auth_code,
        auth_code_file=config.auth_code_file,
        auth_state=config.auth_state,
        token_request_for_individual=config.token_request_for_individual,
        notifier_token_file=config.notifier_token_file,
        token_request_wait_seconds=config.token_request_wait_seconds,
        login_timeout_seconds=config.login_timeout_seconds,
    )
    subscription_manager = SubscriptionManager(
        instruments=config.instruments,
        mode=config.mode,
        batch_size=config.subscription_batch_size,
    )
    zmq_publisher = ZmqTickPublisher(bind_endpoint=config.zmq_bind_endpoint)

    LOGGER.info(
        "bridge.start endpoint=%s instruments=%d mode=%s batch_size=%d",
        config.zmq_bind_endpoint,
        len(config.instruments),
        config.mode,
        config.subscription_batch_size,
    )

    try:
        await connect_loop(
            token_manager=token_manager,
            subscription_manager=subscription_manager,
            zmq_publisher=zmq_publisher,
        )
    finally:
        LOGGER.info("bridge.shutdown published=%d", zmq_publisher.published_count)
        zmq_publisher.close()


def main() -> int:
    try:
        config = BridgeConfig.from_env()
    except BridgeConfigError as exc:
        print(f"[BRIDGE CONFIG ERROR] {exc}", file=sys.stderr)
        return 2

    _configure_logging(config.log_level)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    stop_event = asyncio.Event()

    def _signal_handler(*_args):
        LOGGER.info("bridge.signal.received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows event loop may not support add_signal_handler for all signals.
            signal.signal(sig, lambda *_a: _signal_handler())

    bridge_task = loop.create_task(_run_bridge(config))
    stop_task = loop.create_task(stop_event.wait())

    done, pending = loop.run_until_complete(
        asyncio.wait({bridge_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
    )

    if stop_task in done and not bridge_task.done():
        bridge_task.cancel()
        loop.run_until_complete(asyncio.gather(bridge_task, return_exceptions=True))

    for task in pending:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

    if bridge_task.done() and bridge_task.exception():
        LOGGER.error("bridge.exit.error %s", bridge_task.exception())
        return 1

    LOGGER.info("bridge.exit.ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
