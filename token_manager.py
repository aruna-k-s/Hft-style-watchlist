"""Token lifecycle manager for Upstox bridge runtime."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from login_auth_client import (
    UpstoxLoginAuthClient,
    UpstoxLoginAuthError,
    UpstoxNotifierPayloadError,
)


class TokenRefreshError(RuntimeError):
    """Raised when access token refresh could not be completed."""


class EnvTokenManager:
    """
    Thread-safe token manager.

    Sources (in order on refresh):
    1. token file path (UPSTOX_TOKEN_FILE)
    2. refresh command output (UPSTOX_TOKEN_REFRESH_CMD)
    3. auth-code exchange (UPSTOX_AUTH_CODE / UPSTOX_AUTH_CODE_FILE)
    4. individual token request + notifier payload file

    Refresh command output may be:
    - plain token string
    - JSON with key `access_token` or `token`
    """

    def __init__(
        self,
        initial_access_token: Optional[str] = None,
        token_file: Optional[str] = None,
        refresh_command: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        auth_code: Optional[str] = None,
        auth_code_file: Optional[str] = None,
        auth_state: Optional[str] = None,
        token_request_for_individual: bool = False,
        notifier_token_file: Optional[str] = None,
        token_request_wait_seconds: int = 180,
        login_timeout_seconds: float = 10.0,
        login_client: Optional[UpstoxLoginAuthClient] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._token = (initial_access_token or "").strip() or None
        self._token_file = token_file
        self._refresh_command = refresh_command
        self._client_id = (client_id or "").strip() or None
        self._client_secret = (client_secret or "").strip() or None
        self._redirect_uri = (redirect_uri or "").strip() or None
        self._auth_code = (auth_code or "").strip() or None
        self._auth_code_file = (auth_code_file or "").strip() or None
        self._auth_state = (auth_state or "").strip() or None
        self._token_request_for_individual = bool(token_request_for_individual)
        self._notifier_token_file = (notifier_token_file or "").strip() or None
        self._token_request_wait_seconds = int(token_request_wait_seconds)

        if self._token_request_wait_seconds <= 0:
            raise ValueError("token_request_wait_seconds must be > 0")

        if self._requires_login_client():
            self._login_client = login_client or UpstoxLoginAuthClient(
                timeout_seconds=login_timeout_seconds
            )
        else:
            self._login_client = None

    def get_token(self) -> str:
        with self._lock:
            token = self._token
        if token:
            return token
        return self.refresh_token()

    def invalidate_token(self) -> None:
        with self._lock:
            self._token = None

    def refresh_token(self) -> str:
        token = self._read_token_file()
        if token is None:
            token = self._run_refresh_command()
        if token is None:
            token = self._exchange_auth_code_for_token()
        if token is None:
            token = self._refresh_via_individual_token_request()

        if token is None:
            raise TokenRefreshError(
                "Unable to refresh Upstox access token. "
                "Provide one of: UPSTOX_ACCESS_TOKEN, UPSTOX_TOKEN_FILE, "
                "UPSTOX_TOKEN_REFRESH_CMD, auth-code exchange config "
                "(UPSTOX_CLIENT_ID/UPSTOX_CLIENT_SECRET/UPSTOX_REDIRECT_URI + "
                "UPSTOX_AUTH_CODE or UPSTOX_AUTH_CODE_FILE), or individual token request flow "
                "(UPSTOX_TOKEN_REQUEST_FOR_INDIVIDUAL + notifier payload file)."
            )

        with self._lock:
            self._token = token
        return token

    def _read_token_file(self) -> Optional[str]:
        if not self._token_file:
            return None

        token_path = Path(self._token_file)
        if not token_path.exists():
            return None

        token = token_path.read_text(encoding="utf-8").strip()
        return self._extract_token_from_text(token, strict_notifier_payload=False)

    def _run_refresh_command(self) -> Optional[str]:
        if not self._refresh_command:
            return None

        completed = subprocess.run(
            self._refresh_command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise TokenRefreshError(
                f"UPSTOX_TOKEN_REFRESH_CMD failed with exit code {completed.returncode}. "
                f"stderr={stderr[:500]}"
            )

        stdout = (completed.stdout or "").strip()
        if not stdout:
            raise TokenRefreshError("UPSTOX_TOKEN_REFRESH_CMD returned empty output.")

        token = self._extract_token_from_text(stdout, strict_notifier_payload=False)
        if token is None:
            raise TokenRefreshError(
                "UPSTOX_TOKEN_REFRESH_CMD output did not contain a usable access token."
            )
        return token

    def _exchange_auth_code_for_token(self) -> Optional[str]:
        if not self._has_auth_code_flow():
            return None

        if not self._client_id or not self._client_secret or not self._redirect_uri:
            raise TokenRefreshError(
                "Auth-code token exchange requires UPSTOX_CLIENT_ID, "
                "UPSTOX_CLIENT_SECRET and UPSTOX_REDIRECT_URI."
            )
        if self._login_client is None:
            raise TokenRefreshError("Internal error: login client is not initialized.")

        raw_code_value = self._load_auth_code_value()
        if raw_code_value is None:
            raise TokenRefreshError(
                "Auth-code token exchange configured but no auth code found. "
                "Set UPSTOX_AUTH_CODE or UPSTOX_AUTH_CODE_FILE."
            )

        try:
            code = self._login_client.extract_authorization_code(
                raw_code_value,
                expected_redirect_uri=self._redirect_uri,
                expected_state=self._auth_state,
            )
            response = self._login_client.exchange_code_for_token(
                code=code,
                client_id=self._client_id,
                client_secret=self._client_secret,
                redirect_uri=self._redirect_uri,
            )
        except UpstoxLoginAuthError as exc:
            raise TokenRefreshError(f"Auth-code token exchange failed: {exc}") from exc

        token = (response.access_token or "").strip()
        if not token:
            raise TokenRefreshError(
                "Get Token API succeeded but did not return a non-empty access_token."
            )
        return token

    def _refresh_via_individual_token_request(self) -> Optional[str]:
        if not self._token_request_for_individual:
            return None
        if not self._client_id or not self._client_secret:
            raise TokenRefreshError(
                "UPSTOX_TOKEN_REQUEST_FOR_INDIVIDUAL requires UPSTOX_CLIENT_ID and "
                "UPSTOX_CLIENT_SECRET."
            )
        if not self._notifier_token_file:
            raise TokenRefreshError(
                "UPSTOX_TOKEN_REQUEST_FOR_INDIVIDUAL requires UPSTOX_NOTIFIER_TOKEN_FILE."
            )
        if self._login_client is None:
            raise TokenRefreshError("Internal error: login client is not initialized.")

        token_file_path = Path(self._notifier_token_file)
        initial_mtime_ns = token_file_path.stat().st_mtime_ns if token_file_path.exists() else None

        try:
            self._login_client.initiate_individual_token_request(
                client_id=self._client_id,
                client_secret=self._client_secret,
            )
        except UpstoxLoginAuthError as exc:
            raise TokenRefreshError(f"Access Token Request API call failed: {exc}") from exc

        deadline = time.monotonic() + float(self._token_request_wait_seconds)
        while time.monotonic() < deadline:
            if token_file_path.exists():
                current_mtime_ns = token_file_path.stat().st_mtime_ns
                if initial_mtime_ns is None or current_mtime_ns > initial_mtime_ns:
                    token_text = token_file_path.read_text(encoding="utf-8").strip()
                    token = self._extract_token_from_text(
                        token_text,
                        strict_notifier_payload=True,
                    )
                    if token:
                        return token
            time.sleep(1.0)

        raise TokenRefreshError(
            "Timed out waiting for notifier payload after Access Token Request initiation. "
            "Ensure the configured notifier webhook writes the JSON payload to "
            "UPSTOX_NOTIFIER_TOKEN_FILE before retry."
        )

    def _load_auth_code_value(self) -> Optional[str]:
        if self._auth_code:
            return self._auth_code
        if not self._auth_code_file:
            return None

        code_path = Path(self._auth_code_file)
        if not code_path.exists():
            return None
        return code_path.read_text(encoding="utf-8").strip() or None

    def _extract_token_from_text(self, text: str, *, strict_notifier_payload: bool) -> Optional[str]:
        value = (text or "").strip()
        if not value:
            return None

        if value.startswith("{"):
            try:
                payload = json.loads(value)
            except json.JSONDecodeError as exc:
                raise TokenRefreshError(
                    "Token source looked like JSON but could not be parsed."
                ) from exc

            if not isinstance(payload, dict):
                raise TokenRefreshError("Token source JSON must be an object.")

            if strict_notifier_payload:
                if self._login_client is None:
                    raise TokenRefreshError("Internal error: login client is not initialized.")
                try:
                    parsed = self._login_client.parse_notifier_access_token_payload(
                        payload,
                        expected_client_id=self._client_id,
                    )
                except UpstoxNotifierPayloadError as exc:
                    raise TokenRefreshError(
                        f"Notifier payload validation failed: {exc}"
                    ) from exc
                return parsed.access_token

            token = payload.get("access_token") or payload.get("token")
            if not isinstance(token, str) or not token.strip():
                raise TokenRefreshError(
                    "Token JSON must include non-empty 'access_token' or 'token'."
                )
            return token.strip()

        if strict_notifier_payload:
            raise TokenRefreshError(
                "Notifier token file must contain JSON webhook payload with message_type=access_token."
            )
        return value

    def _has_auth_code_flow(self) -> bool:
        return self._auth_code is not None or self._auth_code_file is not None

    def _requires_login_client(self) -> bool:
        return self._has_auth_code_flow() or self._token_request_for_individual
