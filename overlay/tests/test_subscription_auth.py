"""Claude Pro/Max (`anthropic-claude`) and Grok (`xai-oauth`) subscription sign-in:
authorize/device shapes, token storage + refresh, the wire the two providers build,
and the shared REST surface. No live network — the token, device and identity
endpoints are faked; the Claude loopback callback is exercised for real on its fixed
port (the redirect is registered for that port, so it cannot be moved)."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from coworker.providers import anthropic_auth, xai_auth
from coworker.providers.anthropic_auth import (
    ClaudeAuthError,
    ClaudeSignInRequired,
    ClaudeTokenStore,
)
from coworker.providers.claude_subscription_provider import (
    CLI_SYSTEM_INSTRUCTION,
    ClaudeSubscriptionProvider,
)
from coworker.providers.grok_subscription_provider import GrokSubscriptionProvider
from coworker.providers.xai_auth import (
    XaiAuthError,
    XaiSignInRequired,
    XaiTokenStore,
)
from coworker.secrets import SecretStore
from coworker.server.app import create_app
from coworker.server.manager import SessionManager


def _response(status: int = 200, body: dict | None = None):
    return SimpleNamespace(status_code=status, json=lambda: body or {})


def _jwt(claims: dict) -> str:
    def b64(obj) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
        )

    return f"{b64({'alg': 'none'})}.{b64(claims)}.sig"


# -- Claude: authorize URL ----------------------------------------------------------


def test_claude_authorize_url_shape():
    url = anthropic_auth.build_authorize_url("st4te", "ch4llenge")
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == anthropic_auth.AUTHORIZE_URL
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert q["client_id"] == "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    assert q["redirect_uri"] == "http://localhost:54545/callback"
    assert q["code_challenge_method"] == "S256"
    assert q["code"] == "true"
    # `user:inference` is what makes the grant usable for messages; without it the
    # sign-in succeeds and every completion 403s.
    assert "user:inference" in q["scope"].split(" ")


# -- Claude: sign-in flow -----------------------------------------------------------


async def _hit_claude_callback(query: str) -> str:
    reader, writer = await asyncio.open_connection(
        "127.0.0.1", anthropic_auth.CALLBACK_PORT
    )
    writer.write(f"GET /callback?{query} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    data = await reader.read(-1)
    writer.close()
    return data.decode()


async def test_claude_sign_in_full_flow(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    opened: dict = {}
    exchanged: dict = {}
    monkeypatch.setattr("webbrowser.open", lambda url: opened.update(url=url))

    def fake_token_post(payload, timeout=30.0):
        exchanged.update(payload)
        return _response(
            body={
                "access_token": "at-1",
                "refresh_token": "rt-1",
                "expires_in": 28800,
                "account": {"uuid": "acc-1", "email_address": "user@example.com"},
                "organization": {"uuid": "org-1", "name": "Personal"},
            }
        )

    monkeypatch.setattr(anthropic_auth, "_token_post", fake_token_post)

    task = asyncio.create_task(anthropic_auth.sign_in(secrets))
    while not opened:
        await asyncio.sleep(0.01)
    state = parse_qs(urlsplit(opened["url"]).query)["state"][0]

    # A forged local hit with the wrong state must not consume the flow.
    assert (await _hit_claude_callback("code=evil&state=wrong")).startswith(
        "HTTP/1.1 400"
    )
    assert not task.done()

    assert (await _hit_claude_callback(f"code=c0de&state={state}")).startswith(
        "HTTP/1.1 200"
    )
    assert await task == {"ok": True, "account": "user@example.com"}

    assert exchanged["grant_type"] == "authorization_code"
    assert exchanged["redirect_uri"] == "http://localhost:54545/callback"
    assert exchanged["code_verifier"] and exchanged["state"] == state
    profile = secrets.get("provider:anthropic-claude")
    assert profile["tokens"] == {"access_token": "at-1", "refresh_token": "rt-1"}
    assert profile["account_email"] == "user@example.com"
    assert profile["org_name"] == "Personal"
    # The 30-day absolute grant window is anchored at the interactive login.
    assert profile["grant_expires_at"] > time.time() + 29 * 24 * 3600


async def test_claude_sign_in_falls_back_to_bootstrap_identity(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    opened: dict = {}
    monkeypatch.setattr("webbrowser.open", lambda url: opened.update(url=url))
    monkeypatch.setattr(
        anthropic_auth,
        "_token_post",
        lambda payload, timeout=30.0: _response(
            body={"access_token": "at-1", "refresh_token": "rt-1"}
        ),
    )
    monkeypatch.setattr(
        anthropic_auth,
        "bootstrap_identity",
        lambda token, timeout=30.0: {
            "account_id": "acc-9",
            "account_email": "boot@example.com",
            "org_id": "org-9",
            "org_name": "Bootstrapped",
        },
    )
    task = asyncio.create_task(anthropic_auth.sign_in(secrets))
    while not opened:
        await asyncio.sleep(0.01)
    state = parse_qs(urlsplit(opened["url"]).query)["state"][0]
    await _hit_claude_callback(f"code=c0de&state={state}")
    assert (await task)["account"] == "boot@example.com"
    assert secrets.get("provider:anthropic-claude")["org_name"] == "Bootstrapped"


def test_claude_exchange_accepts_pasted_code_and_state(monkeypatch):
    seen: dict = {}

    def fake_token_post(payload, timeout=30.0):
        seen.update(payload)
        return _response(body={"access_token": "at"})

    monkeypatch.setattr(anthropic_auth, "_token_post", fake_token_post)
    # The vendor's paste-the-code page hands back `code#state`.
    anthropic_auth.exchange_code("c0de#pasted-state", "verifier", "flow-state")
    assert seen["code"] == "c0de"
    assert seen["state"] == "pasted-state"


# -- Claude: token store ------------------------------------------------------------


def test_claude_refresh_happens_before_expiry(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    store = ClaudeTokenStore(secrets)
    store.save({"access_token": "old", "refresh_token": "rt-1", "expires_in": 60}, login=True)
    calls: list[dict] = []

    def fake_token_post(payload, timeout=30.0):
        calls.append(payload)
        return _response(body={"access_token": "new", "expires_in": 28800})

    monkeypatch.setattr(anthropic_auth, "_token_post", fake_token_post)
    # 60s left is inside the refresh margin, so the store rotates instead of
    # handing out a bearer that dies mid-request.
    assert store.access_token() == "new"
    assert calls[0]["grant_type"] == "refresh_token"
    # A refresh that omits the refresh token keeps the stored one.
    assert secrets.get("provider:anthropic-claude")["tokens"]["refresh_token"] == "rt-1"
    # Fresh now: no second call.
    assert store.access_token() == "new"
    assert len(calls) == 1


def test_claude_rejected_refresh_clears_profile(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    store = ClaudeTokenStore(secrets)
    store.save({"access_token": "old", "refresh_token": "rt-1", "expires_in": 10}, login=True)
    monkeypatch.setattr(
        anthropic_auth,
        "_token_post",
        lambda payload, timeout=30.0: _response(400, {"error": "invalid_grant"}),
    )
    with pytest.raises(ClaudeSignInRequired):
        store.access_token()
    assert secrets.get("provider:anthropic-claude") in (None, {})


def test_transient_refresh_failure_keeps_the_sign_in(tmp_path, monkeypatch):
    """A 400 that is NOT a grant rejection must not sign the user out.

    The failure mode this pins: a proxy or a malformed-request answer wiping a working
    subscription mid-session, so the next turn says "not signed in".
    """
    secrets = SecretStore(tmp_path / "s.json")
    store = ClaudeTokenStore(secrets)
    store.save({"access_token": "old", "refresh_token": "rt-1", "expires_in": 10}, login=True)
    monkeypatch.setattr(
        anthropic_auth,
        "_token_post",
        lambda payload, timeout=30.0: _response(400, {"error": "server_error"}),
    )
    with pytest.raises(ClaudeAuthError) as caught:
        store.access_token()
    assert not isinstance(caught.value, ClaudeSignInRequired)
    assert secrets.get("provider:anthropic-claude")["tokens"]["refresh_token"] == "rt-1"


def test_xai_transient_refresh_failure_keeps_the_sign_in(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    store = XaiTokenStore(secrets)
    store.save({"access_token": _jwt({"exp": time.time() + 10}), "refresh_token": "rt"})
    monkeypatch.setattr(xai_auth, "_token_endpoint", "https://auth.x.ai/oauth2/token")
    monkeypatch.setattr(
        xai_auth,
        "_post_form",
        lambda url, data, timeout=30.0: _response(400, {"error": "temporarily_unavailable"}),
    )
    with pytest.raises(XaiAuthError) as caught:
        store.access_token()
    assert not isinstance(caught.value, XaiSignInRequired)
    assert secrets.get("provider:xai-oauth")["tokens"]["refresh_token"] == "rt"


def test_claude_expired_grant_is_refused_without_a_request(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    store = ClaudeTokenStore(secrets)
    store.save({"access_token": "old", "refresh_token": "rt-1", "expires_in": 10})
    secrets.put(
        "provider:anthropic-claude",
        {**secrets.get("provider:anthropic-claude"), "grant_expires_at": int(time.time()) - 1},
    )

    def explode(payload, timeout=30.0):  # pragma: no cover - must not be reached
        raise AssertionError("a dead 30-day grant must not hit the token endpoint")

    monkeypatch.setattr(anthropic_auth, "_token_post", explode)
    with pytest.raises(ClaudeSignInRequired, match="30 days"):
        store.access_token()


def test_claude_verify_maps_http_status(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    assert anthropic_auth.verify(secrets)["state"] == "signed_out"

    ClaudeTokenStore(secrets).save(
        {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}, login=True
    )
    monkeypatch.setattr(
        anthropic_auth,
        "bootstrap_identity",
        lambda token, timeout=10.0: {
            "account_id": "acc-1",
            "account_email": "user@example.com",
            "org_id": "",
            "org_name": "",
        },
    )
    assert anthropic_auth.verify(secrets) == {"ok": True, "account": "user@example.com"}

    def unauthorized(token, timeout=10.0):
        raise ClaudeAuthError("The Claude account endpoint returned HTTP 401.")

    monkeypatch.setattr(anthropic_auth, "bootstrap_identity", unauthorized)
    result = anthropic_auth.verify(secrets)
    assert result["ok"] is False and result["state"] == "expired"


# -- Claude: the wire the provider builds -------------------------------------------


def _claude_provider(tmp_path):
    secrets = SecretStore(tmp_path / "s.json")
    ClaudeTokenStore(secrets).save(
        {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}, login=True
    )
    return ClaudeSubscriptionProvider(secrets=secrets)


def test_claude_request_prepends_cli_identity_and_prefixes_tools(tmp_path):
    provider = _claude_provider(tmp_path)
    kwargs = provider._request_kwargs(
        model="claude-opus-4-8",
        messages=[
            {"role": "system", "content": "You are the FP coworker."},
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "[]"},
        ],
        tools=[
            {
                "type": "function",
                "function": {"name": "web_search", "parameters": {"type": "object"}},
            }
        ],
        settings={},
    )
    # OAuth inference is rejected without the CLI identity block, and the session's
    # own system prompt must survive right behind it.
    assert kwargs["system"][0]["text"] == CLI_SYSTEM_INSTRUCTION
    assert kwargs["system"][1]["text"] == "You are the FP coworker."
    # `web_search` is an Anthropic server tool: unprefixed it is rejected outright.
    assert kwargs["tools"][0]["name"] == "_web_search"
    replayed = [
        block
        for message in kwargs["messages"]
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if block.get("type") == "tool_use"
    ]
    assert [b["name"] for b in replayed] == ["_web_search"]


def test_claude_identity_block_is_not_duplicated(tmp_path):
    provider = _claude_provider(tmp_path)
    blocks = provider._system_blocks(
        [{"type": "text", "text": CLI_SYSTEM_INSTRUCTION}, {"type": "text", "text": "x"}]
    )
    assert [b["text"] for b in blocks] == [CLI_SYSTEM_INSTRUCTION, "x"]


def test_claude_tool_names_are_restored_on_the_way_back(tmp_path):
    provider = _claude_provider(tmp_path)

    class FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use", id="tu_1", name="_web_search", input={"q": "x"}
                    )
                ],
                stop_reason="tool_use",
                usage=SimpleNamespace(input_tokens=1, output_tokens=2),
            )

    provider._client = SimpleNamespace(
        messages=SimpleNamespace(stream=lambda **kwargs: FakeStream())
    )
    provider._injected = True
    turn = provider.complete(
        model="claude-opus-4-8", messages=[{"role": "user", "content": "hi"}]
    )
    # The engine's tool registry knows `web_search`, not the wire name.
    assert [c.name for c in turn.tool_calls] == ["web_search"]


def test_claude_client_sends_bearer_and_betas(tmp_path, monkeypatch):
    provider = _claude_provider(tmp_path)
    client = provider._ensure_client()
    assert client.auth_headers == {"Authorization": "Bearer at"}
    assert "x-api-key" not in {k.lower() for k in client.auth_headers}
    betas = client.default_headers["anthropic-beta"]
    assert "oauth-2025-04-20" in betas and "claude-code-20250219" in betas
    # Subscription tokens have no long-context credit: advertising the 1M beta
    # hard-429s every request on a 1M model.
    assert "context-1m" not in betas
    assert client.default_headers["User-Agent"].startswith("claude-cli/")


# -- xAI: device flow ---------------------------------------------------------------


def test_xai_endpoint_pinning_rejects_foreign_hosts():
    assert (
        xai_auth.validate_endpoint("https://auth.x.ai/oauth2/token", "token_endpoint")
        == "https://auth.x.ai/oauth2/token"
    )
    for bad in ("http://auth.x.ai/t", "https://auth.x.ai.evil.com/t", "https://evil/t"):
        with pytest.raises(XaiAuthError):
            xai_auth.validate_endpoint(bad, "token_endpoint")


async def test_xai_sign_in_polls_until_authorized(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    opened: dict = {}
    monkeypatch.setattr("webbrowser.open", lambda url: opened.update(url=url))
    monkeypatch.setattr(xai_auth, "_token_endpoint", "https://auth.x.ai/oauth2/token")
    monkeypatch.setattr(xai_auth, "DEFAULT_POLL_INTERVAL", 0.01)
    access = _jwt({"exp": time.time() + 3600, "sub": "sub-1"})
    posts: list[tuple[str, dict]] = []

    def fake_post(url, data, timeout=30.0):
        posts.append((url, data))
        if url == xai_auth.DEVICE_CODE_URL:
            return _response(
                body={
                    "device_code": "dev-1",
                    "user_code": "ABCD-1234",
                    "verification_uri": "https://x.ai/device",
                    "verification_uri_complete": "https://x.ai/device?code=ABCD-1234",
                    "interval": 0,
                    "expires_in": 600,
                }
            )
        if len([p for p in posts if p[0] != xai_auth.DEVICE_CODE_URL]) == 1:
            return _response(400, {"error": "authorization_pending"})
        return _response(body={"access_token": access, "refresh_token": "rt-1"})

    monkeypatch.setattr(xai_auth, "_post_form", fake_post)
    monkeypatch.setattr(
        xai_auth,
        "fetch_identity",
        lambda token, timeout=15.0: {"account_id": "sub-1", "account_email": "u@x.ai"},
    )

    result = await xai_auth.sign_in(secrets)
    assert result == {"ok": True, "account": "u@x.ai"}
    # The user code rides the opened URL, so nothing has to be retyped.
    assert opened["url"] == "https://x.ai/device?code=ABCD-1234"
    profile = secrets.get("provider:xai-oauth")
    assert profile["tokens"]["refresh_token"] == "rt-1"
    assert profile["account_id"] == "sub-1"
    # `exp` from the JWT drives proactive refresh — there is no expires_in here.
    assert profile["expires_at"] > time.time() + 3000
    # Pending answers are polled, not treated as failures.
    assert sum(1 for url, _ in posts if url != xai_auth.DEVICE_CODE_URL) == 2


async def test_xai_sign_in_surfaces_denial(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    monkeypatch.setattr("webbrowser.open", lambda url: None)
    monkeypatch.setattr(xai_auth, "_token_endpoint", "https://auth.x.ai/oauth2/token")
    monkeypatch.setattr(xai_auth, "DEFAULT_POLL_INTERVAL", 0.01)

    def fake_post(url, data, timeout=30.0):
        if url == xai_auth.DEVICE_CODE_URL:
            return _response(
                body={
                    "device_code": "dev-1",
                    "user_code": "CODE",
                    "verification_uri": "https://x.ai/device",
                    "interval": 0,
                }
            )
        return _response(400, {"error": "access_denied"})

    monkeypatch.setattr(xai_auth, "_post_form", fake_post)
    with pytest.raises(XaiAuthError, match="denied"):
        await xai_auth.sign_in(secrets, open_browser=False)
    assert not XaiTokenStore(secrets).signed_in()


def test_xai_token_endpoint_comes_from_discovery(monkeypatch):
    monkeypatch.setattr(xai_auth, "_token_endpoint", "")
    import httpx

    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kwargs: _response(
            body={"token_endpoint": "https://auth.x.ai/oauth2/token"}
        ),
    )
    assert xai_auth.token_endpoint() == "https://auth.x.ai/oauth2/token"

    # A tampered discovery document cannot redirect the grant off x.ai.
    monkeypatch.setattr(xai_auth, "_token_endpoint", "")
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kwargs: _response(body={"token_endpoint": "https://evil.test/t"}),
    )
    with pytest.raises(XaiAuthError):
        xai_auth.token_endpoint()


def test_xai_rejected_refresh_clears_profile(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    store = XaiTokenStore(secrets)
    store.save({"access_token": _jwt({"exp": time.time() + 10}), "refresh_token": "rt"})
    monkeypatch.setattr(xai_auth, "_token_endpoint", "https://auth.x.ai/oauth2/token")
    monkeypatch.setattr(
        xai_auth,
        "_post_form",
        lambda url, data, timeout=30.0: _response(400, {"error": "invalid_grant"}),
    )
    with pytest.raises(XaiSignInRequired):
        store.access_token()
    assert secrets.get("provider:xai-oauth") in (None, {})


# -- Grok: the wire the provider builds ---------------------------------------------


def _grok_provider(tmp_path):
    secrets = SecretStore(tmp_path / "s.json")
    XaiTokenStore(secrets).save(
        {"access_token": _jwt({"exp": time.time() + 3600, "sub": "s"}), "refresh_token": "rt"}
    )
    return GrokSubscriptionProvider(secrets=secrets)


def test_grok_request_drops_unsupported_wire_fields(tmp_path):
    provider = _grok_provider(tmp_path)
    kwargs = provider._request_kwargs(
        model="grok-build",
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        settings={"reasoning_effort": "high"},
    )
    # xAI serves no encrypted reasoning, and `grok-build` 400s on reasoning.effort.
    assert "include" not in kwargs
    assert "reasoning" not in kwargs

    kwargs = provider._request_kwargs(
        model="grok-4.6",
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        settings={"reasoning_effort": "minimal"},
    )
    # 4.6 takes effort, but xAI's vocabulary has no "minimal" tier.
    assert kwargs["reasoning"] == {"effort": "low"}


def test_grok_client_uses_the_oauth_bearer_and_endpoint(tmp_path):
    provider = _grok_provider(tmp_path)
    client = provider._ensure_client()
    assert str(client.base_url).rstrip("/") == "https://api.x.ai/v1"
    assert client.api_key.startswith("ey") or "." in client.api_key


# -- shared REST surface ------------------------------------------------------------


def _rest(tmp_path):
    manager = SessionManager(data_dir=tmp_path / "data")
    return manager, TestClient(create_app(manager))


@pytest.mark.parametrize(
    "name,model",
    [("anthropic-claude", "claude-opus-4-8"), ("xai-oauth", "grok-4.6")],
)
def test_subscription_providers_expose_oauth_state(tmp_path, name, model):
    manager, client = _rest(tmp_path)
    row = {p["name"]: p for p in client.get("/v1/providers").json()}[name]
    assert row["auth"] == "oauth" and row["needs_key"] is False
    assert row["signed_in"] is False and row["configured"] is False
    assert model in row["suggested_models"]

    manager.secrets.put(
        f"provider:{name}",
        {"tokens": {"access_token": "a", "refresh_token": "r"}, "account_email": "u@x"},
    )
    row = {p["name"]: p for p in client.get("/v1/providers").json()}[name]
    assert row["signed_in"] is True and row["account"] == "u@x"
    assert "tokens" not in row.get("values", {})  # secrets never leave the store


@pytest.mark.parametrize("name", ["anthropic-claude", "xai-oauth"])
def test_status_and_signout_routes(tmp_path, name):
    manager, client = _rest(tmp_path)
    assert client.get(f"/v1/providers/{name}/status").json()["signed_in"] is False
    manager.secrets.put(
        f"provider:{name}", {"tokens": {"access_token": "a"}, "account_email": "u@x"}
    )
    status = client.get(f"/v1/providers/{name}/status").json()
    assert status["signed_in"] is True and status["account"] == "u@x"
    assert client.post(f"/v1/providers/{name}/signout").json() == {
        "ok": True,
        "had_tokens": True,
    }
    assert client.get(f"/v1/providers/{name}/status").json()["signed_in"] is False


def test_non_oauth_provider_has_no_signin_route(tmp_path):
    _, client = _rest(tmp_path)
    body = client.get("/v1/providers/anthropic/status").json()
    assert body["ok"] is False and "subscription" in body["error"]
    assert client.post("/v1/providers/anthropic/signin").json()["ok"] is False


async def test_signin_promotes_the_plan_model(tmp_path, monkeypatch):
    manager, _ = _rest(tmp_path)

    async def fake_sign_in(secrets, **kwargs):
        ClaudeTokenStore(secrets).save(
            {"access_token": "at", "refresh_token": "rt", "expires_in": 3600},
            login=True,
        )
        return {"ok": True, "account": "user@example.com"}

    monkeypatch.setattr(anthropic_auth, "sign_in", fake_sign_in)
    assert (await manager.oauth_signin("anthropic-claude"))["ok"] is True
    assert "anthropic-claude:claude-opus-4-8" in manager.get_settings()["models"]


async def test_signin_failure_lands_in_status(tmp_path, monkeypatch):
    manager, client = _rest(tmp_path)

    async def fake_sign_in(secrets, **kwargs):
        raise XaiAuthError("Sign-in was denied in the browser.")

    monkeypatch.setattr(xai_auth, "sign_in", fake_sign_in)
    assert (await manager.oauth_signin("xai-oauth"))["ok"] is False
    status = client.get("/v1/providers/xai-oauth/status").json()
    assert "denied" in status["last_error"] and status["authorizing"] is False
    # One provider's failure must not smear onto the others.
    assert client.get("/v1/providers/anthropic-claude/status").json()["last_error"] is None


@pytest.mark.parametrize("name", ["anthropic-claude", "xai-oauth"])
def test_verify_route_reports_signed_out(tmp_path, name):
    _, client = _rest(tmp_path)
    result = client.post("/v1/providers/verify", json={"name": name}).json()
    assert result["ok"] is False and result["state"] == "signed_out"
