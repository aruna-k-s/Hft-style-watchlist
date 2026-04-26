"""Configuration loader for the Upstox WebSocket bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


class BridgeConfigError(RuntimeError):
    """Raised when bridge configuration is missing or invalid."""


@dataclass(frozen=True)
class BridgeConfig:
    instruments: List[str]
    mode: str
    subscription_batch_size: int
    zmq_bind_endpoint: str
    log_level: str
    access_token: str | None
    token_file: str | None
    token_refresh_cmd: str | None
    client_id: str | None
    client_secret: str | None
    redirect_uri: str | None
    auth_code: str | None
    auth_code_file: str | None
    auth_state: str | None
    token_request_for_individual: bool
    notifier_token_file: str | None
    token_request_wait_seconds: int
    login_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        instruments_raw = os.getenv("UPSTOX_INSTRUMENTS", "").strip()
        if not instruments_raw:
            raise BridgeConfigError(
                "Missing UPSTOX_INSTRUMENTS. "
                "Provide a comma-separated list like 'NSE_EQ|INE002A01018,NSE_EQ|INE467B01029'."
            )

        instruments = [item.strip() for item in instruments_raw.split(",") if item.strip()]
        if not instruments:
            raise BridgeConfigError("UPSTOX_INSTRUMENTS did not contain any valid instrument keys.")

        batch_raw = os.getenv("UPSTOX_SUBSCRIPTION_BATCH_SIZE", "100").strip()
        try:
            batch_size = int(batch_raw)
        except ValueError as exc:
            raise BridgeConfigError("UPSTOX_SUBSCRIPTION_BATCH_SIZE must be an integer.") from exc
        if batch_size <= 0:
            raise BridgeConfigError("UPSTOX_SUBSCRIPTION_BATCH_SIZE must be > 0.")

        mode = os.getenv("UPSTOX_MODE", "full").strip() or "full"
        if mode not in {"ltpc", "option_greeks", "full", "full_d30"}:
            raise BridgeConfigError(
                "UPSTOX_MODE must be one of: ltpc, option_greeks, full, full_d30."
            )

        zmq_bind_endpoint = os.getenv("UPSTOX_BRIDGE_ZMQ_BIND", "tcp://*:5555").strip()
        if not zmq_bind_endpoint:
            raise BridgeConfigError("UPSTOX_BRIDGE_ZMQ_BIND cannot be empty.")

        log_level = os.getenv("UPSTOX_BRIDGE_LOG_LEVEL", "INFO").strip().upper() or "INFO"

        access_token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip() or None
        token_file = os.getenv("UPSTOX_TOKEN_FILE", "").strip() or None
        token_refresh_cmd = os.getenv("UPSTOX_TOKEN_REFRESH_CMD", "").strip() or None

        client_id = os.getenv("UPSTOX_CLIENT_ID", "").strip() or None
        client_secret = os.getenv("UPSTOX_CLIENT_SECRET", "").strip() or None
        redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "").strip() or None
        auth_code = os.getenv("UPSTOX_AUTH_CODE", "").strip() or None
        auth_code_file = os.getenv("UPSTOX_AUTH_CODE_FILE", "").strip() or None
        auth_state = os.getenv("UPSTOX_AUTH_STATE", "").strip() or None
        token_request_for_individual = cls._parse_bool_env(
            "UPSTOX_TOKEN_REQUEST_FOR_INDIVIDUAL",
            default=False,
        )
        notifier_token_file = os.getenv("UPSTOX_NOTIFIER_TOKEN_FILE", "").strip() or None

        token_request_wait_raw = os.getenv("UPSTOX_TOKEN_REQUEST_WAIT_SECONDS", "180").strip()
        try:
            token_request_wait_seconds = int(token_request_wait_raw)
        except ValueError as exc:
            raise BridgeConfigError("UPSTOX_TOKEN_REQUEST_WAIT_SECONDS must be an integer.") from exc
        if token_request_wait_seconds <= 0:
            raise BridgeConfigError("UPSTOX_TOKEN_REQUEST_WAIT_SECONDS must be > 0.")

        login_timeout_raw = os.getenv("UPSTOX_LOGIN_TIMEOUT_SECONDS", "10").strip()
        try:
            login_timeout_seconds = float(login_timeout_raw)
        except ValueError as exc:
            raise BridgeConfigError("UPSTOX_LOGIN_TIMEOUT_SECONDS must be a number.") from exc
        if login_timeout_seconds <= 0:
            raise BridgeConfigError("UPSTOX_LOGIN_TIMEOUT_SECONDS must be > 0.")

        auth_code_flow_enabled = auth_code is not None or auth_code_file is not None
        if auth_code is not None and auth_code_file is not None:
            raise BridgeConfigError(
                "Set only one auth code source: UPSTOX_AUTH_CODE or UPSTOX_AUTH_CODE_FILE."
            )
        if auth_code_flow_enabled and (
            client_id is None or client_secret is None or redirect_uri is None
        ):
            raise BridgeConfigError(
                "Auth-code flow requires UPSTOX_CLIENT_ID, UPSTOX_CLIENT_SECRET, "
                "and UPSTOX_REDIRECT_URI."
            )
        if token_request_for_individual and (client_id is None or client_secret is None):
            raise BridgeConfigError(
                "UPSTOX_TOKEN_REQUEST_FOR_INDIVIDUAL requires UPSTOX_CLIENT_ID and "
                "UPSTOX_CLIENT_SECRET."
            )
        if token_request_for_individual and notifier_token_file is None:
            raise BridgeConfigError(
                "UPSTOX_TOKEN_REQUEST_FOR_INDIVIDUAL requires UPSTOX_NOTIFIER_TOKEN_FILE."
            )

        has_legacy_token_source = (
            access_token is not None or token_file is not None or token_refresh_cmd is not None
        )
        if not has_legacy_token_source and not auth_code_flow_enabled and not token_request_for_individual:
            raise BridgeConfigError(
                "No token source configured. Set one of: "
                "UPSTOX_ACCESS_TOKEN, UPSTOX_TOKEN_FILE, UPSTOX_TOKEN_REFRESH_CMD, "
                "auth-code flow (UPSTOX_CLIENT_ID/UPSTOX_CLIENT_SECRET/UPSTOX_REDIRECT_URI "
                "+ UPSTOX_AUTH_CODE or UPSTOX_AUTH_CODE_FILE), "
                "or UPSTOX_TOKEN_REQUEST_FOR_INDIVIDUAL with notifier payload file."
            )

        return cls(
            instruments=instruments,
            mode=mode,
            subscription_batch_size=batch_size,
            zmq_bind_endpoint=zmq_bind_endpoint,
            log_level=log_level,
            access_token=access_token,
            token_file=token_file,
            token_refresh_cmd=token_refresh_cmd,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            auth_code=auth_code,
            auth_code_file=auth_code_file,
            auth_state=auth_state,
            token_request_for_individual=token_request_for_individual,
            notifier_token_file=notifier_token_file,
            token_request_wait_seconds=token_request_wait_seconds,
            login_timeout_seconds=login_timeout_seconds,
        )

    @staticmethod
    def _parse_bool_env(name: str, default: bool) -> bool:
        raw_value = os.getenv(name)
        if raw_value is None:
            return default

        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
        raise BridgeConfigError(
            f"{name} must be one of: 1/0, true/false, yes/no, on/off."
        )
