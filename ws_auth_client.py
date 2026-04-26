"""Upstox WebSocket authorization URL client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict


AUTHORIZE_ENDPOINT = "https://api.upstox.com/v3/feed/market-data-feed/authorize"


class UpstoxAuthError(RuntimeError):
    """Base error for auth URL retrieval failures."""


class TokenExpiredError(UpstoxAuthError):
    """Raised when Upstox rejects the token (401/403)."""


class UpstoxAuthClient:
    """Fetches one-time authorized Upstox WebSocket URLs."""

    def __init__(self, endpoint: str = AUTHORIZE_ENDPOINT, timeout_seconds: float = 10.0) -> None:
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds

    def get_authorized_url(self, access_token: str) -> str:
        """
        Retrieve a fresh authorized_redirect_uri for each connection attempt.

        This MUST be called before every connect/reconnect because the URL includes
        a one-time authorization code.
        """
        if not access_token:
            raise UpstoxAuthError("Access token is required to authorize WebSocket URL.")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        request = urllib.request.Request(self._endpoint, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body_bytes = response.read()
                status_code = response.getcode()
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            body_text = exc.read().decode("utf-8", errors="replace")
            if status_code in (401, 403):
                raise TokenExpiredError(
                    f"Token rejected by Upstox authorize API ({status_code})."
                ) from exc
            raise UpstoxAuthError(
                f"Authorize API failed with status {status_code}. Response: {body_text[:400]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise UpstoxAuthError(f"Authorize API network error: {exc}") from exc

        if status_code != 200:
            raise UpstoxAuthError(f"Authorize API returned unexpected status {status_code}.")

        try:
            payload: Dict[str, Any] = json.loads(body_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise UpstoxAuthError("Authorize API returned non-JSON response.") from exc

        if not isinstance(payload, dict):
            raise UpstoxAuthError("Authorize API response is not a JSON object.")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise UpstoxAuthError("Authorize API response missing object field 'data'.")

        redirect_uri = data.get("authorized_redirect_uri")
        if not isinstance(redirect_uri, str) or not redirect_uri:
            raise UpstoxAuthError(
                "Authorize API response missing string field 'data.authorized_redirect_uri'."
            )

        if not redirect_uri.startswith("wss://"):
            raise UpstoxAuthError(
                "Authorize API returned invalid websocket URL. Expected 'wss://...'."
            )

        return redirect_uri


def get_authorized_url(access_token: str) -> str:
    """Compatibility wrapper for call sites that import a module-level function."""
    return UpstoxAuthClient().get_authorized_url(access_token)
