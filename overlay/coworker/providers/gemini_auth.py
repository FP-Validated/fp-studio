"""Subscription sign-in for the `gemini-code-assist` provider (Google Cloud Code Assist).

Third shape after `codex_auth` (loopback PKCE) and `xai_auth` (device code): Google's CLI
client is a *confidential* OAuth client whose id AND secret ship inside the vendor's own
tooling, the token endpoint is form-encoded, and a usable credential needs one more thing
than tokens — a Cloud Code Assist **project**. `loadCodeAssist`/`onboardUser` resolve (and
if necessary provision) it at sign-in; without it the inference endpoint rejects every
request, so the project id is stored next to the tokens and re-checked on refresh.

Tokens land in the SecretStore profile `provider:gemini-code-assist`.
`gemini_code_assist_provider.py` owns the wire.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import secrets as pysecrets
import time
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlsplit

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"
# The vendor's public CLI client credentials, stored base64 exactly as its own tooling
# ships them (a "secret" that is distributed with the client is not a secret — but the
# token endpoint requires it).
CLIENT_ID = base64.b64decode(
    "NjgxMjU1ODA5Mzk1LW9vOGZ0Mm9wcmRybnA5ZTNhcWY2YXYzaG1kaWIxMzVqLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29t"
).decode("ascii")
CLIENT_SECRET = base64.b64decode("R09DU1BYLTR1SGdNUG0tMW83U2stZ2VWNkN1NWNsWEZzeGw=").decode(
    "ascii"
)
CALLBACK_PORT = 8085
CALLBACK_PATH = "/oauth2callback"
REDIRECT_URI = f"http://127.0.0.1:{CALLBACK_PORT}{CALLBACK_PATH}"
SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
)
SCOPE = " ".join(SCOPES)
PROFILE = "provider:gemini-code-assist"
FLOW_TIMEOUT_SECONDS = 300
REFRESH_MARGIN_SECONDS = 300
# Client fingerprint the Code Assist backend gates rate limits on.
CLIENT_VERSION = "0.46.0"
CLIENT_METADATA = "ideType=IDE_UNSPECIFIED,platform=PLATFORM_UNSPECIFIED,pluginType=GEMINI"
# Project provisioning is a long-running operation; bounded so a stuck backend becomes an
# error instead of an endless sign-in.
POLL_INTERVAL_SECONDS = 5.0
POLL_MAX_ATTEMPTS = 24
_TIER_FREE = "free-tier"
_TIER_LEGACY = "legacy-tier"

SIGNED_OUT_ERROR = (
    "Not signed in to Google — connect your Gemini plan in Settings ▸ Models to use the "
    "subscription provider."
)
EXPIRED_ERROR = "Google session expired — sign in again in Settings ▸ Models."
PLAN_LIMIT_ERROR = (
    "Gemini plan limit reached — the plan's quota window is used up. Wait for it to "
    "reset, upgrade the plan, or switch to an API-key provider."
)
PROJECT_REQUIRED_ERROR = (
    "This Google account needs a Cloud project for Code Assist. Set GOOGLE_CLOUD_PROJECT "
    "(or GOOGLE_CLOUD_PROJECT_ID) and sign in again — see "
    "https://goo.gle/gemini-cli-auth-docs#workspace-gca"
)
PORT_BUSY_ERROR = (
    f"Port {CALLBACK_PORT} is busy, and Google only accepts that exact redirect. Close "
    "the other sign-in (or the app holding the port) and try again."
)


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


class GeminiAuthError(RuntimeError):
    """A subscription-auth failure with a user-readable message."""


class GeminiSignInRequired(GeminiAuthError):
    """No usable tokens — the fix is an explicit sign-in, never a silent browser."""


def client_headers(model: str = "gemini-2.5-pro") -> dict[str, str]:
    """The non-auth headers every Code Assist request carries."""
    import platform

    machine = platform.machine()
    arch = "x64" if machine in ("x86_64", "AMD64") else machine
    return {
        "User-Agent": f"GeminiCLI/{CLIENT_VERSION}/{model} ({platform.system().lower()}; {arch}; terminal)",
        "Client-Metadata": CLIENT_METADATA,
    }


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
        # Without offline+consent Google returns no refresh token on a repeat sign-in.
        "access_type": "offline",
        "prompt": "consent",
    }
    return AUTHORIZE_URL + "?" + urlencode(params)


# -- token endpoint ---------------------------------------------------------------


def _token_post(data: dict[str, str], timeout: float = 30.0) -> Any:
    """One form POST to the token endpoint (module-level so tests stub the wire here)."""
    import httpx

    return httpx.post(
        TOKEN_URL, data=data, headers={"Accept": "application/json"}, timeout=timeout
    )


def exchange_code(code: str, timeout: float = 30.0) -> dict[str, Any]:
    resp = _token_post(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
        timeout,
    )
    if resp.status_code >= 300:
        raise GeminiAuthError(
            f"Sign-in failed — token exchange returned HTTP {resp.status_code}."
        )
    return resp.json()


def fetch_identity(access_token: str, timeout: float = 15.0) -> dict[str, Any]:
    """Signed-in account, and the `verify` probe: authenticates without plan quota."""
    import httpx

    resp = httpx.get(
        USERINFO_URL,
        params={"alt": "json"},
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=timeout,
    )
    if resp.status_code >= 300:
        raise GeminiAuthError(
            f"The Google account endpoint returned HTTP {resp.status_code}."
        )
    body = resp.json() or {}
    return {"account_id": body.get("id") or "", "account_email": body.get("email") or ""}


# -- Code Assist project ----------------------------------------------------------


def _code_assist_post(path: str, token: str, payload: dict[str, Any], timeout: float = 30.0) -> Any:
    import httpx

    return httpx.post(
        f"{CODE_ASSIST_ENDPOINT}/v1internal{path}",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            **client_headers(),
        },
        timeout=timeout,
    )


def _code_assist_get(path: str, token: str, timeout: float = 30.0) -> Any:
    import httpx

    return httpx.get(
        f"{CODE_ASSIST_ENDPOINT}/v1internal/{path}",
        headers={"Authorization": f"Bearer {token}", **client_headers()},
        timeout=timeout,
    )


def _env_project() -> str:
    import os

    for key in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_PROJECT_ID"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return ""


def _default_tier(allowed: Any) -> str:
    if not isinstance(allowed, list) or not allowed:
        return _TIER_LEGACY
    for tier in allowed:
        if isinstance(tier, dict) and tier.get("isDefault"):
            return str(tier.get("id") or _TIER_LEGACY)
    return _TIER_LEGACY


def discover_project(token: str) -> str:
    """The account's Code Assist project, provisioning a free-tier one when needed.

    Mirrors the vendor CLI: `loadCodeAssist` reports an existing project or the tiers the
    account may use; a paid/managed tier requires the operator to name the project through
    the environment, and the free tier is provisioned here through `onboardUser`.
    """
    env_project = _env_project()
    metadata = {
        "ideType": "IDE_UNSPECIFIED",
        "platform": "PLATFORM_UNSPECIFIED",
        "pluginType": "GEMINI",
    }
    load = _code_assist_post(
        ":loadCodeAssist",
        token,
        {
            "cloudaicompanionProject": env_project or None,
            "metadata": {**metadata, "duetProject": env_project or None},
        },
    )
    if load.status_code in (401, 403):
        raise GeminiSignInRequired(EXPIRED_ERROR)
    if load.status_code >= 300:
        raise GeminiAuthError(
            f"Google Code Assist setup failed (HTTP {load.status_code}). {PROJECT_REQUIRED_ERROR}"
        )
    body = load.json() or {}
    if body.get("currentTier"):
        project = body.get("cloudaicompanionProject") or env_project
        if not project:
            raise GeminiAuthError(PROJECT_REQUIRED_ERROR)
        return str(project)

    tier = _default_tier(body.get("allowedTiers"))
    if tier != _TIER_FREE and not env_project:
        raise GeminiAuthError(PROJECT_REQUIRED_ERROR)
    onboard_body: dict[str, Any] = {"tierId": tier, "metadata": dict(metadata)}
    if tier != _TIER_FREE and env_project:
        onboard_body["cloudaicompanionProject"] = env_project
        onboard_body["metadata"]["duetProject"] = env_project
    operation = _code_assist_post(":onboardUser", token, onboard_body)
    if operation.status_code >= 300:
        raise GeminiAuthError(
            f"Google Code Assist provisioning failed (HTTP {operation.status_code})."
        )
    result = operation.json() or {}
    for attempt in range(POLL_MAX_ATTEMPTS):
        if result.get("done"):
            project = (
                ((result.get("response") or {}).get("cloudaicompanionProject") or {}).get("id")
                or env_project
            )
            if not project:
                raise GeminiAuthError(PROJECT_REQUIRED_ERROR)
            return str(project)
        name = result.get("name")
        if not name:
            break
        time.sleep(POLL_INTERVAL_SECONDS)
        polled = _code_assist_get(str(name), token)
        if polled.status_code >= 300:
            raise GeminiAuthError(
                f"Google Code Assist provisioning failed (HTTP {polled.status_code})."
            )
        result = polled.json() or {}
    raise GeminiAuthError(
        "Google Code Assist project provisioning did not finish — try signing in again."
    )


class GeminiTokenStore:
    """Tokens + project in the `provider:gemini-code-assist` SecretStore profile."""

    def __init__(self, secrets: Any) -> None:
        self._secrets = secrets

    def _data(self) -> dict[str, Any]:
        if self._secrets is None:
            return {}
        return self._secrets.get(PROFILE) or {}

    def _merge(self, patch: dict[str, Any]) -> None:
        self._secrets.put(PROFILE, {**self._data(), **patch})

    def signed_in(self) -> bool:
        data = self._data()
        # Tokens without a project cannot serve a single request; that is signed out.
        return bool(data.get("tokens")) and bool(data.get("project"))

    def account_label(self) -> Optional[str]:
        data = self._data()
        return data.get("account_email") or data.get("account_id") or None

    def project(self) -> str:
        return str(self._data().get("project") or "")

    def save(self, tokens: dict[str, Any]) -> None:
        prior = self._data().get("tokens") or {}
        merged = {
            key: (tokens.get(key) or prior.get(key))
            for key in ("access_token", "refresh_token", "id_token")
        }
        merged = {key: value for key, value in merged.items() if value}
        now = int(time.time())
        patch: dict[str, Any] = {"tokens": merged, "tokens_issued_at": now}
        expires_in = tokens.get("expires_in")
        if isinstance(expires_in, (int, float)) and expires_in > 0:
            patch["expires_at"] = now + int(expires_in)
        self._merge(patch)

    def save_identity(self, identity: dict[str, Any]) -> None:
        patch = {key: value for key, value in identity.items() if value}
        if patch:
            self._merge(patch)

    def save_project(self, project: str) -> None:
        if project:
            self._merge({"project": project})

    def clear(self) -> bool:
        if self._secrets is None:
            return False
        return bool(self._secrets.delete(PROFILE))

    def access_token(self) -> tuple[str, str]:
        """(live access token, project). Refreshes near expiry; re-resolves a lost project."""
        data = self._data()
        tokens = data.get("tokens") or {}
        access = tokens.get("access_token") or ""
        if not access and not tokens.get("refresh_token"):
            raise GeminiSignInRequired(SIGNED_OUT_ERROR)
        expires_at = data.get("expires_at")
        if not access or (
            isinstance(expires_at, (int, float))
            and expires_at - time.time() < REFRESH_MARGIN_SECONDS
        ):
            access = self.refresh()
        project = self.project()
        if not project:
            # A credential without a project is unusable; recover it instead of failing
            # every request with the backend's opaque rejection.
            project = discover_project(access)
            self.save_project(project)
        return access, project

    def refresh(self) -> str:
        refresh = (self._data().get("tokens") or {}).get("refresh_token") or ""
        if not refresh:
            self.clear()
            raise GeminiSignInRequired(EXPIRED_ERROR)
        try:
            resp = _token_post(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                }
            )
        except Exception as exc:
            raise GeminiAuthError(
                f"Couldn't reach Google to refresh the session ({exc.__class__.__name__})."
            ) from exc
        if 400 <= resp.status_code < 500:
            if not _grant_is_dead(resp):
                raise GeminiAuthError(
                    f"Google session refresh failed (HTTP {resp.status_code}) — try again."
                )
            self.clear()
            raise GeminiSignInRequired(EXPIRED_ERROR)
        if resp.status_code >= 300:
            raise GeminiAuthError(
                f"Google session refresh failed (HTTP {resp.status_code}) — try again."
            )
        self.save(resp.json())
        return (self._data().get("tokens") or {}).get("access_token") or ""


def token_store(secrets: Any) -> GeminiTokenStore:
    """Uniform entry point for the generic OAuth-provider plumbing in the manager."""
    return GeminiTokenStore(secrets)


# -- interactive sign-in flow -----------------------------------------------------

last_authorize_url: Optional[str] = None
_active_server: Optional[asyncio.AbstractServer] = None

_PAGE = """<!doctype html><meta charset="utf-8"><title>FP Studio</title>
<body style="font-family: system-ui; margin: 4rem auto; max-width: 28rem; text-align: center;">
<h2>{title}</h2><p>{body}</p></body>"""


def _http_response(status: str, title: str, body: str) -> bytes:
    html = _PAGE.format(title=title, body=body).encode("utf-8")
    head = (
        f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(html)}\r\nConnection: close\r\n\r\n"
    )
    return head.encode("ascii") + html


async def _start_callback_server(
    expected_state: str,
) -> tuple[asyncio.AbstractServer, "asyncio.Future[str]"]:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
            parts = request_line.decode("ascii", errors="replace").split()
            target = urlsplit(parts[1] if len(parts) > 1 else "/")
            if target.path != CALLBACK_PATH:
                writer.write(_http_response("404 Not Found", "Not found", ""))
                return
            query = parse_qs(target.query)
            error = (query.get("error") or [""])[0]
            code = (query.get("code") or [""])[0]
            state = (query.get("state") or [""])[0]
            if error:
                writer.write(
                    _http_response(
                        "400 Bad Request",
                        "Sign-in failed",
                        "Google reported an error. Return to FP Studio and try again.",
                    )
                )
                if not future.done():
                    future.set_exception(
                        GeminiAuthError(f"Sign-in failed — Google returned: {error}")
                    )
                return
            if not code or not pysecrets.compare_digest(state, expected_state):
                writer.write(
                    _http_response(
                        "400 Bad Request",
                        "Nothing waiting for this sign-in",
                        "The sign-in may have timed out. Return to FP Studio and start it again.",
                    )
                )
                return
            writer.write(
                _http_response(
                    "200 OK", "Signed in", "You can close this tab and return to FP Studio."
                )
            )
            if not future.done():
                future.set_result(code)
        finally:
            try:
                await writer.drain()
                writer.close()
            except Exception:
                pass

    try:
        server = await asyncio.start_server(handle, "127.0.0.1", CALLBACK_PORT)
    except OSError as exc:
        raise GeminiAuthError(PORT_BUSY_ERROR) from exc
    return server, future


async def sign_in(
    secrets: Any,
    *,
    timeout: float = FLOW_TIMEOUT_SECONDS,
    open_browser: bool = True,
) -> dict[str, Any]:
    """Loopback browser flow, then resolve the Code Assist project before declaring
    success — tokens alone are not a usable credential here."""
    global last_authorize_url, _active_server
    if _active_server is not None:
        _active_server.close()
        await _active_server.wait_closed()
        _active_server = None
    state = pysecrets.token_urlsafe(24)
    url = build_authorize_url(state)
    last_authorize_url = url
    server, code_future = await _start_callback_server(state)
    _active_server = server
    try:
        if open_browser:
            import webbrowser

            logger.info("gemini auth: opening browser for sign-in")
            await asyncio.get_running_loop().run_in_executor(None, webbrowser.open, url)
        try:
            code = await asyncio.wait_for(code_future, timeout)
        except asyncio.TimeoutError:
            raise GeminiAuthError(
                "Sign-in timed out — the browser window was not completed in "
                f"{int(timeout) // 60} minutes."
            )
    finally:
        server.close()
        await server.wait_closed()
        if _active_server is server:
            _active_server = None
    tokens = await asyncio.to_thread(exchange_code, code)
    store = GeminiTokenStore(secrets)
    store.save(tokens)
    access = (store._data().get("tokens") or {}).get("access_token") or ""
    if not access:
        store.clear()
        raise GeminiAuthError("Sign-in failed — the token response had no access token.")
    try:
        store.save_project(await asyncio.to_thread(discover_project, access))
    except GeminiAuthError:
        # Without a project nothing can be served, so the profile must not look signed in.
        store.clear()
        raise
    try:
        store.save_identity(await asyncio.to_thread(fetch_identity, access))
    except Exception as exc:  # pragma: no cover - network-dependent
        logger.info("gemini auth: userinfo unavailable (%s)", exc)
    return {"ok": True, "account": store.account_label()}


# -- verify probe -----------------------------------------------------------------


def verify(secrets: Any, timeout: float = 10.0) -> dict[str, Any]:
    store = GeminiTokenStore(secrets)
    if not store.signed_in():
        return {"ok": False, "error": SIGNED_OUT_ERROR, "state": "signed_out"}
    try:
        token, _project = store.access_token()
    except GeminiSignInRequired as exc:
        return {"ok": False, "error": str(exc), "state": "signed_out"}
    except GeminiAuthError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        identity = fetch_identity(token, timeout)
    except GeminiAuthError as exc:
        message = str(exc)
        if "HTTP 401" in message or "HTTP 403" in message:
            return {"ok": False, "error": EXPIRED_ERROR, "state": "expired"}
        return {"ok": False, "error": message}
    except Exception as exc:
        return {"ok": False, "error": f"Couldn't reach Google ({exc.__class__.__name__})."}
    store.save_identity(identity)
    return {"ok": True, "account": store.account_label() or None}


def status(secrets: Any) -> dict[str, Any]:
    store = GeminiTokenStore(secrets)
    return {
        "signed_in": store.signed_in(),
        "account": store.account_label(),
        "project": store.project() or None,
        "authorize_url": last_authorize_url,
    }


__all__ = [
    "CLIENT_ID",
    "CODE_ASSIST_ENDPOINT",
    "EXPIRED_ERROR",
    "GeminiAuthError",
    "GeminiSignInRequired",
    "GeminiTokenStore",
    "PLAN_LIMIT_ERROR",
    "PROFILE",
    "PROJECT_REQUIRED_ERROR",
    "SIGNED_OUT_ERROR",
    "build_authorize_url",
    "client_headers",
    "discover_project",
    "exchange_code",
    "fetch_identity",
    "sign_in",
    "status",
    "token_store",
    "verify",
]
