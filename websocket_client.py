"""Upstox WebSocket client with strict connect/subscribe/reconnect lifecycle."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Optional, Protocol

import websockets

import proto_decoder
from ws_auth_client import TokenExpiredError, UpstoxAuthClient


LOGGER = logging.getLogger(__name__)


class TokenManagerProtocol(Protocol):
    def get_token(self) -> str:
        ...

    def invalidate_token(self) -> None:
        ...


class ZmqPublisherProtocol(Protocol):
    def publish(self, tick: dict) -> Any:
        ...


class UpstoxWebSocketClient:
    """Coordinates token -> auth URL -> WebSocket -> subscription -> decode -> publish."""

    def __init__(
        self,
        token_manager: TokenManagerProtocol,
        subscription_manager,
        zmq_publisher: ZmqPublisherProtocol,
        auth_client: Optional[UpstoxAuthClient] = None,
        initial_backoff_seconds: int = 2,
        max_backoff_seconds: int = 30,
    ) -> None:
        if not hasattr(token_manager, "get_token"):
            raise RuntimeError("token_manager must implement get_token().")
        if not hasattr(token_manager, "invalidate_token"):
            raise RuntimeError("token_manager must implement invalidate_token() for 401 recovery.")

        self._token_manager = token_manager
        self._subscription_manager = subscription_manager
        self._zmq_publisher = zmq_publisher
        self._auth_client = auth_client or UpstoxAuthClient()
        self._initial_backoff_seconds = initial_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds

    async def connect_loop(self) -> None:
        backoff = self._initial_backoff_seconds
        has_connected_once = False

        while True:
            try:
                token = await self._call_maybe_async(
                    self._token_manager.get_token,
                    prefer_thread_for_sync=True,
                )
                if not token:
                    raise RuntimeError("token_manager.get_token() returned empty token.")

                # Strict rule: fetch fresh authorized URL before every connect/reconnect.
                wss_url = await asyncio.to_thread(self._auth_client.get_authorized_url, token)

                LOGGER.info("bridge.connect.start")
                is_reconnect = has_connected_once
                has_connected_once = True
                await self._connect_and_stream(wss_url, is_reconnect=is_reconnect)
                backoff = self._initial_backoff_seconds

            except Exception as exc:
                await self._handle_error(exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._max_backoff_seconds)

    async def _connect_and_stream(self, wss_url: str, is_reconnect: bool) -> None:
        async with websockets.connect(
            wss_url,
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            LOGGER.info("bridge.connect.ok")

            if is_reconnect and hasattr(self._subscription_manager, "resubscribe"):
                await self._subscription_manager.resubscribe(ws)
            else:
                await self._subscription_manager.subscribe(ws)
            LOGGER.info("bridge.subscribe.ok instruments=%d", len(self._subscription_manager.instruments))

            async for message in ws:
                await self._process_message(message)

    async def _process_message(self, message: Any) -> None:
        if isinstance(message, str):
            # Upstox feed payloads are protobuf binary frames; ignore text safely.
            LOGGER.debug("bridge.decode.skip_text_message")
            return

        if not isinstance(message, (bytes, bytearray, memoryview)):
            LOGGER.debug("bridge.decode.skip_unknown_message_type type=%s", type(message).__name__)
            return

        decoded_ticks = proto_decoder.decode_many(bytes(message))
        if not decoded_ticks:
            return

        for tick in decoded_ticks:
            await self._publish_tick(tick)
            LOGGER.debug("bridge.decode.ok symbol=%s", tick["symbol"])

    async def _publish_tick(self, tick: dict) -> None:
        publish_result = self._zmq_publisher.publish(tick)
        if inspect.isawaitable(publish_result):
            await publish_result

    async def _handle_error(self, exc: Exception) -> None:
        LOGGER.exception("bridge.error type=%s message=%s", type(exc).__name__, exc)

        if isinstance(exc, TokenExpiredError) or self._is_unauthorized_ws_error(exc):
            try:
                await self._call_maybe_async(
                    self._token_manager.invalidate_token,
                    prefer_thread_for_sync=True,
                )
                refresh_fn = getattr(self._token_manager, "refresh_token", None)
                if callable(refresh_fn):
                    await self._call_maybe_async(
                        refresh_fn,
                        prefer_thread_for_sync=True,
                    )
                LOGGER.warning("bridge.token.refreshed")
            except Exception as refresh_exc:
                LOGGER.error(
                    "bridge.token.refresh_failed type=%s message=%s",
                    type(refresh_exc).__name__,
                    refresh_exc,
                )

    @staticmethod
    def _is_unauthorized_ws_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if status_code is None:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
        return status_code in (401, 403)

    @staticmethod
    async def _call_maybe_async(
        callable_obj,
        *args,
        prefer_thread_for_sync: bool = False,
        **kwargs,
    ):
        if prefer_thread_for_sync and not inspect.iscoroutinefunction(callable_obj):
            return await asyncio.to_thread(callable_obj, *args, **kwargs)

        result = callable_obj(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result


async def connect_loop(
    token_manager: TokenManagerProtocol,
    subscription_manager,
    zmq_publisher: ZmqPublisherProtocol,
    auth_client: Optional[UpstoxAuthClient] = None,
) -> None:
    """Functional entry point for existing call sites."""
    client = UpstoxWebSocketClient(
        token_manager=token_manager,
        subscription_manager=subscription_manager,
        zmq_publisher=zmq_publisher,
        auth_client=auth_client,
    )
    await client.connect_loop()
