"""Subscription sign-in for the `xai-oauth` provider (SuperGrok / X Premium+).

xAI does not offer a loopback code flow for its CLI client id — it uses the RFC 8628
**device authorization** grant, so the shape differs from `codex_auth`/`anthropic_auth`:

  - No local callback server and no PKCE. We POST for a device code, hand the user a
    `verification_uri_complete` (the code is already embedded) plus the bare code to
    type if they open the page elsewhere, then poll the token endpoint.
  - The token endpoint is not hardcoded: it comes from the issuer's OIDC discovery
    document and is pinned to an `x.ai` host before use, so a tampered discovery
    response cannot redirect the grant.
  - Access tokens are JWTs; `exp` drives proactive refresh (there is no `expires_in`
    on every response).

Tokens land in the SecretStore profile `provider:xai-oauth`. Inference is owned by
`grok_subscription_provider.py`; this module only authenticates.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any, Optional
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

ISSUER = "https://auth.x.ai"
DISCOVERY_URL = ISSUER + "/.well-known/openid-configuration"
DEVICE_CODE_URL = ISSUER + "/oauth2/device/code"
USERINFO_URL = ISSUER + "/oauth2/userinfo"
# The public CLI client id (ships in the vendor's own tooling — not a secret).
CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
SCOPES = (
    "openid",
    "profile",
    "email",
    "offline_access",
    # The two that make the grant usable for Grok inference on a subscription.
    "grok-cli:access",
    "api:access",
)
SCOPE = " ".join(SCOPES)
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
PROFILE = "provider:xai-oauth"
FLOW_TIMEOUT_SECONDS = 600
# Poll interval floor when the device response omits `interval`.
DEFAULT_POLL_INTERVAL = 5.0
REFRESH_MARGIN_SECONDS = 300

SIGNED_OUT_ERROR = (
    "Not signed in to xAI — connect your SuperGrok or X Premium+ account in "
    "Settings ▸ Models to use the subscription provider."
)
EXPIRED_ERROR = "xAI session expired — sign in again in Settings ▸ Models."
PLAN_LIMIT_ERROR = (
    "Grok subscription limit reached — the plan's usage window is used up. Wait for "
    "it to reset, upgrade the plan, or switch to an API-key provider."
)
DENIED_ERROR = "Sign-in was denied in the browser."
DEVICE_EXPIRED_ERROR = "The device code expired — start the sign-in again."


# A refresh may fail because the grant is dead (only a new sign-in recovers it) or because
# the network/endpoint misbehaved. Only the first may erase a working sign-in: clearing the
# profile on a transient 400 would silently sign the user out mid-session.
_DEAD_GRANT_ERRORS = frozenset(
    {"invalid_grant", "invalid_client", "unauthorized_client", "invalid_request"}
)


def _grant_is_dead(resp: Any) -> bool:
    if resp.status_code in (401, 403):
        return True
    try:
        body = resp.json() or {}
    except Exception:
        return False
    return str((body or {}).get("error") or "") in _DEAD_GRANT_ERRORS


class XaiAuthError(RuntimeError):
    """A subscription-auth failure with a user-readable message."""


class XaiSignInRequired(XaiAuthError):
    """No usable tokens — the fix is an explicit sign-in, never a silent browser."""


# -- endpoint pinning + discovery ---------------------------------------------------


def validate_endpoint(url: str, field: str) -> str:
    """HTTPS on `x.ai` (or a subdomain), or it does not get used.

    Discovery is fetched over the network; without this a hijacked document could
    point the device grant — and the tokens — at an attacker's host.
    """
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not (host == "x.ai" or host.endswith(".x.ai")):
        raise XaiAuthError(f"xAI sign-in rejected an untrusted {field}: {url!r}")
    return url


def _discover_token_endpoint(timeout: float = 15.0) -> str:
    import httpx

    try:
        resp = httpx.get(
            DISCOVERY_URL, headers={"Accept": "application/json"}, timeout=timeout
        )
    except Exception as exc:
        raise XaiAuthError(
            f"Couldn't reach the xAI sign-in service ({exc.__class__.__name__})."
        ) from exc
    if resp.status_code >= 300:
        raise XaiAuthError(
            f"The xAI sign-in service returned HTTP {resp.status_code} for discovery."
        )
    endpoint = (resp.json() or {}).get("token_endpoint") or ""
    return validate_endpoint(endpoint, "token_endpoint")


def token_endpoint(timeout: float = 15.0) -> str:
    """Discovered token endpoint, cached per process (it is a constant in practice)."""
    global _token_endpoint
    if not _token_endpoint:
        _token_endpoint = _discover_token_endpoint(timeout)
    return _token_endpoint


_token_endpoint: str = ""


# -- JWT helpers --------------------------------------------------------------------


def _jwt_claims(token: str) -> dict[str, Any]:
    """Decode a JWT payload WITHOUT verifying it — we read `exp`/`sub` for routing
    only; the backend is the one verifying signatures."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return claims if isinstance(claims, dict) else {}
    except Exception:
        return {}


# -- token endpoint calls -----------------------------------------------------------


def _post_form(url: str, data: dict[str, str], timeout: float = 30.0) -> Any:
    """One form POST (module-level so tests stub the wire here)."""
    import httpx

    return httpx.post(
        url, data=data, headers={"Accept": "application/json"}, timeout=timeout
    )


def request_device_code(timeout: float = 30.0) -> dict[str, Any]:
    """Start the device grant → {device_code, user_code, verification_uri, …}."""
    resp = _post_form(
        DEVICE_CODE_URL, {"client_id": CLIENT_ID, "scope": SCOPE}, timeout
    )
    if resp.status_code >= 300:
        raise XaiAuthError(
            f"Sign-in failed — device authorization returned HTTP {resp.status_code}."
        )
    body = resp.json() or {}
    for required in ("device_code", "user_code", "verification_uri"):
        if not body.get(required):
            raise XaiAuthError(
                "Sign-in failed — the device authorization response was incomplete."
            )
    return body


def poll_token(device_code: str, timeout: float = 30.0) -> dict[str, Any]:
    """One device-code poll. Returns the token set, or `{}` while still pending.

    RFC 8628: `authorization_pending`/`slow_down` are normal, everything else is fatal
    for this attempt.
    """
    resp = _post_form(
        token_endpoint(),
        {
            "grant_type": DEVICE_GRANT_TYPE,
            "client_id": CLIENT_ID,
            "device_code": device_code,
        },
        timeout,
    )
    try:
        body = resp.json() or {}
    except Exception:
        body = {}
    error = body.get("error")
    if resp.status_code < 300 and not error:
        return body
    if error in ("authorization_pending", "slow_down"):
        return {"_pending": error}
    if error == "access_denied":
        raise XaiAuthError(DENIED_ERROR)
    if error == "expired_token":
        raise XaiAuthError(DEVICE_EXPIRED_ERROR)
    detail = body.get("error_description") or error or f"HTTP {resp.status_code}"
    raise XaiAuthError(f"Sign-in failed — xAI returned: {detail}")


def fetch_identity(access_token: str, timeout: float = 15.0) -> dict[str, Any]:
    """OIDC userinfo → {account_id, account_email}. Also the `verify` probe: it
    authenticates the bearer without spending plan quota."""
    import httpx

    resp = httpx.get(
        USERINFO_URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        timeout=timeout,
    )
    if resp.status_code >= 300:
        raise XaiAuthError(f"The xAI account endpoint returned HTTP {resp.status_code}.")
    body = resp.json() or {}
    return {
        "account_id": body.get("sub") or "",
        "account_email": body.get("email") or "",
    }


class XaiTokenStore:
    """Token set + account metadata in the `provider:xai-oauth` SecretStore profile.

    `access_token()` is what the provider calls per request: a live bearer, refreshed
    proactively near the JWT `exp`, with the profile cleared to a clean signed-out
    state when the refresh token is rejected.
    """

    def __init__(self, secrets: Any) -> None:
        self._secrets = secrets

    def _data(self) -> dict[str, Any]:
        if self._secrets is None:
            return {}
        return self._secrets.get(PROFILE) or {}

    def _merge(self, patch: dict[str, Any]) -> None:
        self._secrets.put(PROFILE, {**self._data(), **patch})

    def signed_in(self) -> bool:
        return bool(self._data().get("tokens"))

    def account_label(self) -> Optional[str]:
        data = self._data()
        return data.get("account_email") or data.get("account_id") or None

    def save(self, tokens: dict[str, Any]) -> None:
        """Persist a token response, keeping prior values a refresh omitted."""
        prior = self._data().get("tokens") or {}
        merged = {
            key: (tokens.get(key) or prior.get(key))
            for key in ("access_token", "refresh_token", "id_token")
        }
        merged = {key: value for key, value in merged.items() if value}
        now = int(time.time())
        patch: dict[str, Any] = {"tokens": merged, "tokens_issued_at": now}
        claims = _jwt_claims(merged.get("access_token") or "")
        exp = claims.get("exp")
        if isinstance(exp, (int, float)):
            patch["expires_at"] = int(exp)
        elif isinstance(tokens.get("expires_in"), (int, float)):
            patch["expires_at"] = now + int(tokens["expires_in"])
        subject = claims.get("sub") or self._data().get("account_id")
        if subject:
            patch["account_id"] = str(subject)
        self._merge(patch)

    def save_identity(self, identity: dict[str, Any]) -> None:
        patch = {key: value for key, value in identity.items() if value}
        if patch:
            self._merge(patch)

    def clear(self) -> bool:
        if self._secrets is None:
            return False
        return bool(self._secrets.delete(PROFILE))

    def access_token(self) -> str:
        data = self._data()
        tokens = data.get("tokens") or {}
        access = tokens.get("access_token") or ""
        if not access and not tokens.get("refresh_token"):
            raise XaiSignInRequired(SIGNED_OUT_ERROR)
        expires_at = data.get("expires_at")
        stale = not access or (
            isinstance(expires_at, (int, float))
            and expires_at - time.time() < REFRESH_MARGIN_SECONDS
        )
        return self.refresh() if stale else access

    def refresh(self) -> str:
        refresh = (self._data().get("tokens") or {}).get("refresh_token") or ""
        if not refresh:
            self.clear()
            raise XaiSignInRequired(EXPIRED_ERROR)
        try:
            resp = _post_form(
                token_endpoint(),
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": CLIENT_ID,
                },
            )
        except XaiAuthError:
            raise
        except Exception as exc:
            raise XaiAuthError(
                f"Couldn't reach xAI to refresh the session ({exc.__class__.__name__})."
            ) from exc
        if 400 <= resp.status_code < 500:
            if not _grant_is_dead(resp):
                raise XaiAuthError(
                    f"xAI session refresh failed (HTTP {resp.status_code}) — try again."
                )
            self.clear()
            raise XaiSignInRequired(EXPIRED_ERROR)
        if resp.status_code >= 300:
            raise XaiAuthError(
                f"xAI session refresh failed (HTTP {resp.status_code}) — try again."
            )
        self.save(resp.json())
        return (self._data().get("tokens") or {}).get("access_token") or ""


def token_store(secrets: Any) -> XaiTokenStore:
    """Uniform entry point for the generic OAuth-provider plumbing in the manager."""
    return XaiTokenStore(secrets)


# -- interactive sign-in flow -------------------------------------------------------

# Surfaced over REST so the GUI can reopen the page and show the code: a device flow
# has no redirect, so the user code IS part of the affordance.
last_authorize_url: Optional[str] = None
last_user_code: Optional[str] = None


async def sign_in(
    secrets: Any,
    *,
    timeout: float = FLOW_TIMEOUT_SECONDS,
    open_browser: bool = True,
) -> dict[str, Any]:
    """Run the device grant: request a code, open the page, poll until authorized."""
    global last_authorize_url, last_user_code
    device = await asyncio.to_thread(request_device_code)
    url = device.get("verification_uri_complete") or device["verification_uri"]
    last_authorize_url = url
    last_user_code = device.get("user_code")
    interval = device.get("interval")
    delay = float(interval) if isinstance(interval, (int, float)) and interval else DEFAULT_POLL_INTERVAL
    expires_in = device.get("expires_in")
    deadline = time.monotonic() + min(
        timeout,
        float(expires_in) if isinstance(expires_in, (int, float)) and expires_in else timeout,
    )
    if open_browser:
        import webbrowser

        logger.info("xai auth: opening browser for device authorization")
        await asyncio.get_running_loop().run_in_executor(None, webbrowser.open, url)
    tokens: dict[str, Any] = {}
    while True:
        if time.monotonic() >= deadline:
            raise XaiAuthError(
                "Sign-in timed out — the browser authorization was not completed in "
                f"{int(timeout) // 60} minutes."
            )
        await asyncio.sleep(delay)
        result = await asyncio.to_thread(poll_token, device["device_code"])
        pending = result.get("_pending")
        if pending == "slow_down":
            # RFC 8628: the server is asking for a longer interval, not failing.
            delay += 5.0
            continue
        if pending:
            continue
        tokens = result
        break
    store = XaiTokenStore(secrets)
    store.save(tokens)
    if not (store._data().get("tokens") or {}).get("access_token"):
        store.clear()
        raise XaiAuthError("Sign-in failed — the token response had no access token.")
    try:
        store.save_identity(
            await asyncio.to_thread(fetch_identity, store.access_token())
        )
    except Exception as exc:  # pragma: no cover - network-dependent
        # Cosmetic: the account label stays empty, the grant is still usable.
        logger.info("xai auth: userinfo unavailable (%s)", exc)
    last_user_code = None
    return {"ok": True, "account": store.account_label()}


# -- verify probe -------------------------------------------------------------------


def verify(secrets: Any, timeout: float = 10.0) -> dict[str, Any]:
    """Test-button probe: one authenticated userinfo read, no inference."""
    store = XaiTokenStore(secrets)
    if not store.signed_in():
        return {"ok": False, "error": SIGNED_OUT_ERROR, "state": "signed_out"}
    try:
        token = store.access_token()
    except XaiSignInRequired as exc:
        return {"ok": False, "error": str(exc), "state": "signed_out"}
    except XaiAuthError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        identity = fetch_identity(token, timeout)
    except XaiAuthError as exc:
        message = str(exc)
        if "HTTP 401" in message or "HTTP 403" in message:
            return {"ok": False, "error": EXPIRED_ERROR, "state": "expired"}
        return {"ok": False, "error": message}
    except Exception as exc:
        return {"ok": False, "error": f"Couldn't reach xAI ({exc.__class__.__name__})."}
    store.save_identity(identity)
    return {"ok": True, "account": store.account_label() or None}


def status(secrets: Any) -> dict[str, Any]:
    """Sign-in state for the Settings pane (no network)."""
    store = XaiTokenStore(secrets)
    return {
        "signed_in": store.signed_in(),
        "account": store.account_label(),
        "authorize_url": last_authorize_url,
        "user_code": last_user_code,
    }


__all__ = [
    "CLIENT_ID",
    "EXPIRED_ERROR",
    "PLAN_LIMIT_ERROR",
    "PROFILE",
    "SIGNED_OUT_ERROR",
    "XaiAuthError",
    "XaiSignInRequired",
    "XaiTokenStore",
    "fetch_identity",
    "poll_token",
    "request_device_code",
    "sign_in",
    "status",
    "token_endpoint",
    "token_store",
    "validate_endpoint",
    "verify",
]
