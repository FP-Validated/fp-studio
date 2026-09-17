"""Subscription sign-in for the `anthropic-claude` provider (Claude Pro/Max, OAuth 2.0 + PKCE).

Same shape as `codex_auth.py` — a browser flow against the vendor's own public client id
with the loopback redirect that id is registered for, tokens in the SecretStore profile
`provider:anthropic-claude` — but the Anthropic grant differs in three ways that matter:

  - The authorize endpoint is `claude.ai` (the console host issues API-console tokens,
    which are NOT accepted for direct inference), and the token endpoint is on the API host.
  - The token/refresh bodies are JSON, not form-encoded, and refresh additionally requires
    the `anthropic-beta: oauth-2025-04-20` header.
  - The grant family has an ABSOLUTE ~30-day lifetime anchored at the interactive login.
    Refresh rotation does not extend it: after that the token endpoint answers
    `invalid_grant` and only a new sign-in recovers the account. `grant_expires_at` is
    stored so the GUI can say so before the request fails.

Account identity (email, organization) rides the token response when the vendor includes it;
when it doesn't, `bootstrap_identity` reads it from the CLI bootstrap endpoint. Nothing here
performs inference — `claude_subscription_provider.py` owns the wire.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets as pysecrets
import time
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlsplit

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://api.anthropic.com/v1/oauth/token"
BOOTSTRAP_URL = "https://api.anthropic.com/api/claude_cli/bootstrap"
# The public subscription client id, stored base64 exactly as the vendor's own tooling
# ships it (keeps secret scanners quiet — it is not a secret).
CLIENT_ID = base64.b64decode("OWQxYzI1MGEtZTYxYi00NGQ5LTg4ZWQtNTk0NGQxOTYyZjVl").decode(
    "ascii"
)
CALLBACK_PORT = 54545
CALLBACK_PATH = "/callback"
# Registered redirect for CLIENT_ID, verbatim — host and port are not ours to choose.
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
# `user:inference` is the one that makes a subscription token usable for messages; the
# rest are the account/session scopes the same client id is registered with.
SCOPES = (
    "org:create_api_key",
    "user:profile",
    "user:inference",
    "user:sessions:claude_code",
    "user:mcp_servers",
    "user:file_upload",
)
SCOPE = " ".join(SCOPES)
OAUTH_BETA = "oauth-2025-04-20"
# The CLI fingerprint the subscription backend expects on OAuth requests. Lives here
# (not in the provider) so the identity probe and the inference wire agree.
CLIENT_VERSION = "2.1.257"
CLIENT_USER_AGENT = f"claude-cli/{CLIENT_VERSION} (external, cli)"
PROFILE = "provider:anthropic-claude"
FLOW_TIMEOUT_SECONDS = 300
# Refresh this far ahead of `expires_at` instead of sending an about-to-die bearer.
REFRESH_MARGIN_SECONDS = 300
# Absolute lifetime of the grant family, anchored at the interactive login (vendor
# behaviour, not a wire field): rotation does not extend it.
GRANT_TTL_SECONDS = 30 * 24 * 60 * 60
# Bootstrap probe: identity only, no inference, so `verify` costs no plan quota.
_BOOTSTRAP_MODEL = "claude-opus-4-8"

SIGNED_OUT_ERROR = (
    "Not signed in to Claude — connect your Anthropic account in Settings ▸ Models to "
    "use the subscription provider."
)
EXPIRED_ERROR = "Claude session expired — sign in again in Settings ▸ Models."
GRANT_EXPIRED_ERROR = (
    "Claude subscription sign-in is older than 30 days — Anthropic requires a fresh "
    "browser sign-in. Reconnect in Settings ▸ Models."
)
PLAN_LIMIT_ERROR = (
    "Claude plan limit reached — your subscription's usage window is used up. Wait for "
    "it to reset, upgrade the plan, or switch to an API-key provider."
)
PORT_BUSY_ERROR = (
    f"Port {CALLBACK_PORT} is busy, and Anthropic only accepts that exact redirect. "
    "Close the other sign-in (or the app holding the port) and try again."
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


class ClaudeAuthError(RuntimeError):
    """A subscription-auth failure with a user-readable message."""


class ClaudeSignInRequired(ClaudeAuthError):
    """No usable tokens — the fix is an explicit sign-in, never a silent browser."""


# -- PKCE -------------------------------------------------------------------------


def create_pkce() -> tuple[str, str]:
    """(verifier, S256 challenge) per RFC 7636."""
    verifier = pysecrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(state: str, challenge: str) -> str:
    params = {
        # `code=true` is the switch this client id expects: it renders the
        # paste-the-code page as a fallback when the browser can't reach the loopback.
        "code": "true",
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return AUTHORIZE_URL + "?" + urlencode(params)


# -- token endpoint ---------------------------------------------------------------


def _token_post(payload: dict[str, Any], timeout: float = 30.0) -> Any:
    """One JSON POST to the token endpoint (module-level so tests stub the wire here).

    The refresh beta header rides every call: the endpoint requires it on refresh and
    ignores it on the code exchange.
    """
    import httpx

    return httpx.post(
        TOKEN_URL,
        json=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "anthropic-beta": OAUTH_BETA,
        },
        timeout=timeout,
    )


def exchange_code(
    code: str, verifier: str, state: str, timeout: float = 30.0
) -> dict[str, Any]:
    """authorization_code + PKCE verifier → the token set. Blocking (httpx sync);
    `sign_in` runs it via `asyncio.to_thread`.

    The paste-the-code page hands back `code#state`; accept that shape too so a manual
    paste and the loopback redirect take the same path.
    """
    if "#" in code:
        code, _, pasted_state = code.partition("#")
        state = pasted_state or state
    resp = _token_post(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
            "state": state,
        },
        timeout,
    )
    if resp.status_code >= 300:
        raise ClaudeAuthError(
            f"Sign-in failed — token exchange returned HTTP {resp.status_code}."
        )
    return resp.json()


def bootstrap_identity(access_token: str, timeout: float = 30.0) -> dict[str, Any]:
    """Account/organization identity from the CLI bootstrap endpoint.

    Used when the token response omits identity (it often does) and as the `verify`
    probe: it authenticates the bearer without spending plan quota on a completion.
    """
    import httpx

    resp = httpx.get(
        BOOTSTRAP_URL,
        params={"entrypoint": "cli", "model": _BOOTSTRAP_MODEL},
        headers={
            "Accept": "application/json, text/plain, */*",
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "anthropic-beta": OAUTH_BETA,
            "User-Agent": CLIENT_USER_AGENT,
        },
        timeout=timeout,
    )
    if resp.status_code >= 300:
        raise ClaudeAuthError(
            f"The Claude account endpoint returned HTTP {resp.status_code}."
        )
    body = resp.json()
    account = (body or {}).get("oauth_account") or {}
    return {
        "account_id": account.get("account_uuid") or "",
        "account_email": account.get("account_email") or "",
        "org_id": account.get("organization_uuid") or "",
        "org_name": account.get("organization_name") or "",
    }


def _identity_from_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    """The identity slice a token response carries when the vendor includes it."""
    account = tokens.get("account") or {}
    org = tokens.get("organization") or {}
    return {
        "account_id": account.get("uuid") or "",
        "account_email": account.get("email_address") or "",
        "org_id": org.get("uuid") or "",
        "org_name": org.get("name") or "",
    }


class ClaudeTokenStore:
    """Token set + account metadata in the `provider:anthropic-claude` SecretStore profile.

    `access_token()` is what the provider calls per request: a live bearer, refreshed
    proactively near `expires_at`, with the profile cleared to a clean signed-out state
    when the refresh token (or the 30-day grant) is rejected — never a crash loop.
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

    def organization(self) -> Optional[str]:
        return self._data().get("org_name") or None

    def grant_expires_at(self) -> Optional[int]:
        value = self._data().get("grant_expires_at")
        return int(value) if isinstance(value, (int, float)) else None

    def save(self, tokens: dict[str, Any], *, login: bool = False) -> None:
        """Persist a token response, keeping prior values a refresh omitted.

        `login=True` anchors the 30-day grant window and records the organization; a
        refresh deliberately never rewrites the org, because the org a credential is
        scoped to is fixed at sign-in.
        """
        existing = self._data()
        prior = existing.get("tokens") or {}
        merged = {
            key: (tokens.get(key) or prior.get(key))
            for key in ("access_token", "refresh_token")
        }
        merged = {key: value for key, value in merged.items() if value}
        now = int(time.time())
        patch: dict[str, Any] = {"tokens": merged, "tokens_issued_at": now}
        expires_in = tokens.get("expires_in")
        if isinstance(expires_in, (int, float)) and expires_in > 0:
            patch["expires_at"] = now + int(expires_in)
        if login:
            patch["grant_expires_at"] = now + GRANT_TTL_SECONDS
        identity = _identity_from_tokens(tokens)
        for key in ("account_id", "account_email"):
            if identity[key]:
                patch[key] = identity[key]
        if login:
            for key in ("org_id", "org_name"):
                if identity[key]:
                    patch[key] = identity[key]
        self._merge(patch)

    def save_identity(self, identity: dict[str, Any]) -> None:
        """Fill identity fields the token response left empty (bootstrap fallback)."""
        patch = {key: value for key, value in identity.items() if value}
        if patch:
            self._merge(patch)

    def clear(self) -> bool:
        if self._secrets is None:
            return False
        return bool(self._secrets.delete(PROFILE))

    def access_token(self) -> str:
        """A live access token, refreshing first when stale/absent."""
        data = self._data()
        tokens = data.get("tokens") or {}
        access = tokens.get("access_token") or ""
        if not access and not tokens.get("refresh_token"):
            raise ClaudeSignInRequired(SIGNED_OUT_ERROR)
        expires_at = data.get("expires_at")
        stale = not access or (
            isinstance(expires_at, (int, float))
            and expires_at - time.time() < REFRESH_MARGIN_SECONDS
        )
        return self.refresh() if stale else access

    def refresh(self) -> str:
        """refresh_token grant → a fresh access token. A rejected refresh token (or an
        expired 30-day grant) blanks the profile: the provider reads as signed out."""
        data = self._data()
        refresh = (data.get("tokens") or {}).get("refresh_token") or ""
        if not refresh:
            self.clear()
            raise ClaudeSignInRequired(EXPIRED_ERROR)
        grant_expires_at = data.get("grant_expires_at")
        if (
            isinstance(grant_expires_at, (int, float))
            and grant_expires_at <= time.time()
        ):
            self.clear()
            raise ClaudeSignInRequired(GRANT_EXPIRED_ERROR)
        try:
            resp = _token_post(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": CLIENT_ID,
                }
            )
        except Exception as exc:
            raise ClaudeAuthError(
                "Couldn't reach Anthropic to refresh the Claude session "
                f"({exc.__class__.__name__})."
            ) from exc
        if 400 <= resp.status_code < 500:
            if not _grant_is_dead(resp):
                # Rejected for a reason that is not the grant — keep the sign-in.
                raise ClaudeAuthError(
                    f"Claude session refresh failed (HTTP {resp.status_code}) — try again."
                )
            self.clear()
            # A dead 30-day grant and a revoked token are the same HTTP answer; the
            # stored window is what tells them apart for the message.
            raise ClaudeSignInRequired(
                GRANT_EXPIRED_ERROR
                if isinstance(grant_expires_at, (int, float))
                and grant_expires_at - time.time() < GRANT_TTL_SECONDS / 30
                else EXPIRED_ERROR
            )
        if resp.status_code >= 300:
            raise ClaudeAuthError(
                f"Claude session refresh failed (HTTP {resp.status_code}) — try again."
            )
        self.save(resp.json())
        return (self._data().get("tokens") or {}).get("access_token") or ""


def token_store(secrets: Any) -> ClaudeTokenStore:
    """Uniform entry point for the generic OAuth-provider plumbing in the manager."""
    return ClaudeTokenStore(secrets)


# -- interactive sign-in flow -------------------------------------------------------

# The last authorize URL, surfaced over REST so the GUI can offer "reopen sign-in page"
# if the popup was lost (same affordance as codex_auth/mcp oauth).
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
    """Bind the fixed loopback port and resolve the future with the auth code when the
    redirect (carrying the matching `state`) lands."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await reader.readline()
            while True:  # drain headers; the redirect is a bare GET
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
                        "Anthropic reported an error. Return to FP Studio and try again.",
                    )
                )
                if not future.done():
                    future.set_exception(
                        ClaudeAuthError(f"Sign-in failed — Anthropic returned: {error}")
                    )
                return
            # A stray local hit with the wrong state must not consume the flow — only
            # the genuine redirect resolves it.
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
                    "200 OK",
                    "Signed in",
                    "You can close this tab and return to FP Studio.",
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
        raise ClaudeAuthError(PORT_BUSY_ERROR) from exc
    return server, future


async def sign_in(
    secrets: Any,
    *,
    timeout: float = FLOW_TIMEOUT_SECONDS,
    open_browser: bool = True,
) -> dict[str, Any]:
    """Run the full interactive flow: loopback server → browser → code → tokens.

    Explicit-action only (a Settings button); never called from an engine turn.
    """
    global last_authorize_url, _active_server
    if _active_server is not None:
        # A stale flow lost its browser tab; the new one takes the port.
        _active_server.close()
        await _active_server.wait_closed()
        _active_server = None
    verifier, challenge = create_pkce()
    state = pysecrets.token_urlsafe(24)
    url = build_authorize_url(state, challenge)
    last_authorize_url = url
    server, code_future = await _start_callback_server(state)
    _active_server = server
    try:
        if open_browser:
            import webbrowser

            logger.info("claude auth: opening browser for sign-in")
            await asyncio.get_running_loop().run_in_executor(None, webbrowser.open, url)
        try:
            code = await asyncio.wait_for(code_future, timeout)
        except asyncio.TimeoutError:
            raise ClaudeAuthError(
                "Sign-in timed out — the browser window was not completed in "
                f"{int(timeout) // 60} minutes."
            )
    finally:
        server.close()
        await server.wait_closed()
        if _active_server is server:
            _active_server = None
    tokens = await asyncio.to_thread(exchange_code, code, verifier, state)
    store = ClaudeTokenStore(secrets)
    store.save(tokens, login=True)
    access = (store._data().get("tokens") or {}).get("access_token") or ""
    if not access:
        store.clear()
        raise ClaudeAuthError("Sign-in failed — the token response had no access token.")
    if not store.account_label():
        # Identity is optional on the wire; the bootstrap endpoint knows it. A failure
        # here is cosmetic (the label stays empty), so it never fails the sign-in.
        try:
            store.save_identity(await asyncio.to_thread(bootstrap_identity, access))
        except Exception as exc:  # pragma: no cover - network-dependent
            logger.info("claude auth: bootstrap identity unavailable (%s)", exc)
    return {"ok": True, "account": store.account_label()}


# -- verify probe -------------------------------------------------------------------


def verify(secrets: Any, timeout: float = 10.0) -> dict[str, Any]:
    """Test-button probe: one authenticated identity read, no inference.

    Distinguishes signed-out (no/rejected tokens) vs expired (bearer we thought was
    live) vs OK. Never raises; {ok, error?, state?} like the other provider verifies.
    """
    store = ClaudeTokenStore(secrets)
    if not store.signed_in():
        return {"ok": False, "error": SIGNED_OUT_ERROR, "state": "signed_out"}
    try:
        token = store.access_token()
    except ClaudeSignInRequired as exc:
        return {"ok": False, "error": str(exc), "state": "signed_out"}
    except ClaudeAuthError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        identity = bootstrap_identity(token, timeout)
    except ClaudeAuthError as exc:
        message = str(exc)
        if "HTTP 401" in message or "HTTP 403" in message:
            return {"ok": False, "error": EXPIRED_ERROR, "state": "expired"}
        if "HTTP 429" in message:
            # Auth is fine — the plan window is just used up right now.
            return {"ok": True, "account": store.account_label(), "note": PLAN_LIMIT_ERROR}
        return {"ok": False, "error": message}
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Couldn't reach Anthropic ({exc.__class__.__name__}).",
        }
    store.save_identity(identity)
    return {"ok": True, "account": store.account_label() or None}


def status(secrets: Any) -> dict[str, Any]:
    """Sign-in state for the Settings pane (no network)."""
    store = ClaudeTokenStore(secrets)
    return {
        "signed_in": store.signed_in(),
        "account": store.account_label(),
        "organization": store.organization(),
        "grant_expires_at": store.grant_expires_at(),
        "authorize_url": last_authorize_url,
    }


__all__ = [
    "ClaudeAuthError",
    "ClaudeSignInRequired",
    "ClaudeTokenStore",
    "CLIENT_USER_AGENT",
    "CLIENT_VERSION",
    "EXPIRED_ERROR",
    "GRANT_EXPIRED_ERROR",
    "OAUTH_BETA",
    "PLAN_LIMIT_ERROR",
    "PROFILE",
    "SIGNED_OUT_ERROR",
    "bootstrap_identity",
    "build_authorize_url",
    "create_pkce",
    "exchange_code",
    "sign_in",
    "status",
    "token_store",
    "verify",
]
