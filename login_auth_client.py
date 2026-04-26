"""Upstox OAuth/login client for auth-code exchange and token-request flows."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


AUTHORIZE_DIALOG_ENDPOINT = "https://api.upstox.com/v2/login/authorization/dialog"
TOKEN_EXCHANGE_ENDPOINT = "https://api.upstox.com/v2/login/authorization/token"
TOKEN_REQUEST_ENDPOINT_TEMPLATE = "https://api.upstox.com/v3/login/auth/token/request/{client_id}"


class UpstoxLoginAuthError(RuntimeError):
    """Base error for Upstox login/auth operations."""


class UpstoxTokenExchangeError(UpstoxLoginAuthError):
    """Raised when auth-code token exchange fails."""


class UpstoxTokenRequestError(UpstoxLoginAuthError):
    """Raised when individual-user token request flow fails."""


class UpstoxNotifierPayloadError(UpstoxLoginAuthError):
    """Raised when notifier webhook payload is invalid."""


@dataclass(frozen=True)
class TokenExchangeResponse:
    access_token: str
    extended_token: Optional[str]
    raw: Dict[str, Any]


@dataclass(frozen=True)
class TokenRequestResponse:
    authorization_expiry: str
    notifier_url: str
    raw: Dict[str, Any]


@dataclass(frozen=True)
class NotifierAccessTokenPayload:
    client_id: str
    access_token: str
    expires_at: str
    issued_at: str
    user_id: Optional[str]
    token_type: Optional[str]
    raw: Dict[str, Any]


class UpstoxLoginAuthClient:
    """Client for Upstox OAuth login APIs documented under Authentication/Login."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def build_authorize_url(client_id: str, redirect_uri: str, state: Optional[str] = None) -> str:
        """Build /v2/login/authorization/dialog URL with required query parameters."""
        client_id = (client_id or "").strip()
        redirect_uri = (redirect_uri or "").strip()
        if not client_id:
            raise UpstoxLoginAuthError("client_id is required to build authorize URL.")
        if not redirect_uri:
            raise UpstoxLoginAuthError("redirect_uri is required to build authorize URL.")

        query = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        }
        if state is not None and state != "":
            query["state"] = state

        return f"{AUTHORIZE_DIALOG_ENDPOINT}?{urllib.parse.urlencode(query)}"

    @staticmethod
    def extract_authorization_code(
        callback_value: str,
        *,
        expected_redirect_uri: Optional[str] = None,
        expected_state: Optional[str] = None,
    ) -> str:
        """
        Extract authorization code from callback URL or return a raw code string as-is.

        Expected formats:
        - full redirect URL containing ?code=...
        - raw code value
        """
        raw_value = (callback_value or "").strip()
        if not raw_value:
            raise UpstoxLoginAuthError("Authorization callback/code value is empty.")

        if "://" not in raw_value and "code=" not in raw_value and "&" not in raw_value:
            return raw_value

        parsed = urllib.parse.urlparse(raw_value)
        query_map = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

        # Support plain query-string input like "code=xxx&state=yyy".
        if not query_map and ("=" in raw_value):
            query_map = urllib.parse.parse_qs(raw_value, keep_blank_values=True)

        if expected_redirect_uri and parsed.scheme and parsed.netloc:
            expected = urllib.parse.urlparse(expected_redirect_uri)
            if (parsed.scheme, parsed.netloc, parsed.path) != (
                expected.scheme,
                expected.netloc,
                expected.path,
            ):
                raise UpstoxLoginAuthError(
                    "Authorization callback redirect URI does not match configured redirect URI."
                )

        if expected_state is not None:
            state_values = query_map.get("state", [])
            state_value = state_values[0] if state_values else None
            if state_value != expected_state:
                raise UpstoxLoginAuthError("Authorization callback state does not match expected state.")

        code_values = query_map.get("code", [])
        code = code_values[0].strip() if code_values else ""
        if not code:
            raise UpstoxLoginAuthError("Authorization callback does not contain 'code' query parameter.")
        return code

    def exchange_code_for_token(
        self,
        *,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> TokenExchangeResponse:
        """Call /v2/login/authorization/token with authorization_code grant."""
        code = (code or "").strip()
        client_id = (client_id or "").strip()
        client_secret = (client_secret or "").strip()
        redirect_uri = (redirect_uri or "").strip()

        if not code:
            raise UpstoxTokenExchangeError("code is required for token exchange.")
        if not client_id or not client_secret or not redirect_uri:
            raise UpstoxTokenExchangeError(
                "client_id, client_secret, and redirect_uri are required for token exchange."
            )

        form_body = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")

        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        request = urllib.request.Request(
            TOKEN_EXCHANGE_ENDPOINT,
            data=form_body,
            headers=headers,
            method="POST",
        )

        payload = self._request_json(request, UpstoxTokenExchangeError)
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise UpstoxTokenExchangeError(
                "Get Token API response missing non-empty string field 'access_token'."
            )

        extended_token = payload.get("extended_token")
        if extended_token is not None and not isinstance(extended_token, str):
            raise UpstoxTokenExchangeError(
                "Get Token API response field 'extended_token' must be string when present."
            )

        return TokenExchangeResponse(
            access_token=access_token.strip(),
            extended_token=extended_token.strip() if isinstance(extended_token, str) else None,
            raw=payload,
        )

    def initiate_individual_token_request(
        self,
        *,
        client_id: str,
        client_secret: str,
    ) -> TokenRequestResponse:
        """
        Call /v3/login/auth/token/request/{client_id} for individual-user token request flow.
        """
        client_id = (client_id or "").strip()
        client_secret = (client_secret or "").strip()

        if not client_id:
            raise UpstoxTokenRequestError("client_id is required for access token request flow.")
        if not client_secret:
            raise UpstoxTokenRequestError("client_secret is required for access token request flow.")

        endpoint = TOKEN_REQUEST_ENDPOINT_TEMPLATE.format(
            client_id=urllib.parse.quote(client_id, safe="")
        )
        body = json.dumps({"client_secret": client_secret}).encode("utf-8")
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")

        payload = self._request_json(request, UpstoxTokenRequestError)

        status = payload.get("status")
        data = payload.get("data")
        if status != "success" or not isinstance(data, dict):
            raise UpstoxTokenRequestError(
                "Access Token Request API response missing expected success payload."
            )

        authorization_expiry = data.get("authorization_expiry")
        notifier_url = data.get("notifier_url")
        if not isinstance(authorization_expiry, str) or not authorization_expiry.strip():
            raise UpstoxTokenRequestError(
                "Access Token Request API response missing string field 'data.authorization_expiry'."
            )
        if not isinstance(notifier_url, str) or not notifier_url.strip():
            raise UpstoxTokenRequestError(
                "Access Token Request API response missing string field 'data.notifier_url'."
            )

        return TokenRequestResponse(
            authorization_expiry=authorization_expiry.strip(),
            notifier_url=notifier_url.strip(),
            raw=payload,
        )

    @staticmethod
    def parse_notifier_access_token_payload(
        payload: Mapping[str, Any],
        *,
        expected_client_id: Optional[str] = None,
    ) -> NotifierAccessTokenPayload:
        """Validate and parse notifier webhook payload carrying access token."""
        if not isinstance(payload, Mapping):
            raise UpstoxNotifierPayloadError("Notifier payload must be a JSON object.")

        message_type = payload.get("message_type")
        if message_type != "access_token":
            raise UpstoxNotifierPayloadError(
                "Notifier payload message_type must be 'access_token'."
            )

        client_id = payload.get("client_id")
        access_token = payload.get("access_token")
        expires_at = payload.get("expires_at")
        issued_at = payload.get("issued_at")

        if not isinstance(client_id, str) or not client_id.strip():
            raise UpstoxNotifierPayloadError("Notifier payload missing non-empty 'client_id'.")
        if expected_client_id and client_id.strip() != expected_client_id:
            raise UpstoxNotifierPayloadError("Notifier payload client_id does not match expected client_id.")
        if not isinstance(access_token, str) or not access_token.strip():
            raise UpstoxNotifierPayloadError("Notifier payload missing non-empty 'access_token'.")
        if not isinstance(expires_at, str) or not expires_at.strip():
            raise UpstoxNotifierPayloadError("Notifier payload missing non-empty 'expires_at'.")
        if not isinstance(issued_at, str) or not issued_at.strip():
            raise UpstoxNotifierPayloadError("Notifier payload missing non-empty 'issued_at'.")

        token_type = payload.get("token_type")
        if token_type is not None and not isinstance(token_type, str):
            raise UpstoxNotifierPayloadError("Notifier payload field 'token_type' must be string when present.")

        user_id = payload.get("user_id")
        if user_id is not None and not isinstance(user_id, str):
            raise UpstoxNotifierPayloadError("Notifier payload field 'user_id' must be string when present.")

        return NotifierAccessTokenPayload(
            client_id=client_id.strip(),
            access_token=access_token.strip(),
            expires_at=expires_at.strip(),
            issued_at=issued_at.strip(),
            user_id=user_id.strip() if isinstance(user_id, str) else None,
            token_type=token_type.strip() if isinstance(token_type, str) else None,
            raw=dict(payload),
        )

    def _request_json(self, request: urllib.request.Request, error_cls):
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body_bytes = response.read()
                status_code = response.getcode()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise error_cls(
                f"HTTP {exc.code} from {request.full_url}. Response: {body[:600]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise error_cls(f"Network error calling {request.full_url}: {exc}") from exc

        if status_code not in (200, 201):
            raise error_cls(
                f"Unexpected status {status_code} from {request.full_url}."
            )

        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise error_cls(f"Non-JSON response from {request.full_url}.") from exc

        if not isinstance(payload, dict):
            raise error_cls(f"Response from {request.full_url} must be a JSON object.")

        return payload
