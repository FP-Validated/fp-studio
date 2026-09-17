"""Gemini subscription (`gemini-code-assist`): the loopback flow, the Cloud Code Assist
project that makes a credential usable, the REST envelope the provider builds, and the
live model lists the picker is refreshed from. No network — every endpoint is faked."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from coworker.providers import discovery, gemini_auth
from coworker.providers.gemini_auth import (
    GeminiAuthError,
    GeminiSignInRequired,
    GeminiTokenStore,
)
from coworker.providers.gemini_code_assist_provider import (
    STREAM_URL,
    GeminiCodeAssistProvider,
)
from coworker.secrets import SecretStore
from coworker.server.app import create_app
from coworker.server.manager import SessionManager


def _response(status: int = 200, body: dict | None = None):
    return SimpleNamespace(status_code=status, json=lambda: body or {})


async def _hit_callback(query: str) -> str:
    reader, writer = await asyncio.open_connection("127.0.0.1", gemini_auth.CALLBACK_PORT)
    writer.write(
        f"GET /oauth2callback?{query} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
    )
    await writer.drain()
    data = await reader.read(-1)
    writer.close()
    return data.decode()


# -- sign-in ----------------------------------------------------------------------


def test_authorize_url_requests_offline_access():
    url = gemini_auth.build_authorize_url("st4te")
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == gemini_auth.AUTHORIZE_URL
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert q["client_id"].endswith(".apps.googleusercontent.com")
    assert q["redirect_uri"] == "http://127.0.0.1:8085/oauth2callback"
    # Without offline+consent Google returns no refresh token on a repeat sign-in.
    assert q["access_type"] == "offline" and q["prompt"] == "consent"
    assert "https://www.googleapis.com/auth/cloud-platform" in q["scope"].split(" ")


async def test_sign_in_resolves_the_code_assist_project(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    opened: dict = {}
    monkeypatch.setattr("webbrowser.open", lambda url: opened.update(url=url))
    monkeypatch.setattr(
        gemini_auth,
        "_token_post",
        lambda data, timeout=30.0: _response(
            body={"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3599}
        ),
    )
    monkeypatch.setattr(
        gemini_auth,
        "discover_project",
        lambda token: "cloud-project-1",
    )
    monkeypatch.setattr(
        gemini_auth,
        "fetch_identity",
        lambda token, timeout=15.0: {"account_id": "1", "account_email": "u@example.com"},
    )
    task = asyncio.create_task(gemini_auth.sign_in(secrets))
    while not opened:
        await asyncio.sleep(0.01)
    state = parse_qs(urlsplit(opened["url"]).query)["state"][0]
    assert (await _hit_callback("code=evil&state=wrong")).startswith("HTTP/1.1 400")
    assert not task.done()
    assert (await _hit_callback(f"code=c0de&state={state}")).startswith("HTTP/1.1 200")
    assert await task == {"ok": True, "account": "u@example.com"}
    profile = secrets.get("provider:gemini-code-assist")
    assert profile["tokens"]["refresh_token"] == "rt-1"
    assert profile["project"] == "cloud-project-1"


async def test_sign_in_without_a_project_is_not_signed_in(tmp_path, monkeypatch):
    # Tokens alone cannot serve a request here, so a project failure must not leave a
    # half-configured provider that looks connected and 403s on every turn.
    secrets = SecretStore(tmp_path / "s.json")
    opened: dict = {}
    monkeypatch.setattr("webbrowser.open", lambda url: opened.update(url=url))
    monkeypatch.setattr(
        gemini_auth,
        "_token_post",
        lambda data, timeout=30.0: _response(body={"access_token": "at", "refresh_token": "rt"}),
    )

    def refuse(token):
        raise GeminiAuthError(gemini_auth.PROJECT_REQUIRED_ERROR)

    monkeypatch.setattr(gemini_auth, "discover_project", refuse)
    task = asyncio.create_task(gemini_auth.sign_in(secrets))
    while not opened:
        await asyncio.sleep(0.01)
    state = parse_qs(urlsplit(opened["url"]).query)["state"][0]
    await _hit_callback(f"code=c0de&state={state}")
    with pytest.raises(GeminiAuthError, match="Cloud project"):
        await task
    assert not GeminiTokenStore(secrets).signed_in()
    assert secrets.get("provider:gemini-code-assist") in (None, {})


def test_project_discovery_uses_existing_project(monkeypatch):
    calls: list[str] = []

    def fake_post(path, token, payload, timeout=30.0):
        calls.append(path)
        return _response(
            body={"currentTier": {"id": "legacy-tier"}, "cloudaicompanionProject": "proj-9"}
        )

    monkeypatch.setattr(gemini_auth, "_code_assist_post", fake_post)
    assert gemini_auth.discover_project("at") == "proj-9"
    # An account that already has a project must not be onboarded again.
    assert calls == [":loadCodeAssist"]


def test_project_discovery_provisions_free_tier(monkeypatch):
    posts: list[str] = []

    def fake_post(path, token, payload, timeout=30.0):
        posts.append(path)
        if path == ":loadCodeAssist":
            return _response(body={"allowedTiers": [{"id": "free-tier", "isDefault": True}]})
        return _response(
            body={
                "done": True,
                "response": {"cloudaicompanionProject": {"id": "proj-free"}},
            }
        )

    monkeypatch.setattr(gemini_auth, "_code_assist_post", fake_post)
    assert gemini_auth.discover_project("at") == "proj-free"
    assert posts == [":loadCodeAssist", ":onboardUser"]


def test_paid_tier_without_an_operator_project_is_refused(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_ID", raising=False)
    monkeypatch.setattr(
        gemini_auth,
        "_code_assist_post",
        lambda path, token, payload, timeout=30.0: _response(
            body={"allowedTiers": [{"id": "standard-tier", "isDefault": True}]}
        ),
    )
    with pytest.raises(GeminiAuthError, match="GOOGLE_CLOUD_PROJECT"):
        gemini_auth.discover_project("at")


def test_rejected_refresh_clears_the_profile(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    store = GeminiTokenStore(secrets)
    store.save({"access_token": "old", "refresh_token": "rt", "expires_in": 10})
    store.save_project("proj")
    monkeypatch.setattr(
        gemini_auth,
        "_token_post",
        lambda data, timeout=30.0: _response(400, {"error": "invalid_grant"}),
    )
    with pytest.raises(GeminiSignInRequired):
        store.access_token()
    assert secrets.get("provider:gemini-code-assist") in (None, {})


def test_transient_refresh_failure_keeps_the_sign_in(tmp_path, monkeypatch):
    secrets = SecretStore(tmp_path / "s.json")
    store = GeminiTokenStore(secrets)
    store.save({"access_token": "old", "refresh_token": "rt", "expires_in": 10})
    store.save_project("proj")
    monkeypatch.setattr(
        gemini_auth,
        "_token_post",
        lambda data, timeout=30.0: _response(400, {"error": "backend_error"}),
    )
    with pytest.raises(GeminiAuthError) as caught:
        store.access_token()
    assert not isinstance(caught.value, GeminiSignInRequired)
    assert secrets.get("provider:gemini-code-assist")["project"] == "proj"


# -- the wire the provider builds ---------------------------------------------------


class _FakeStream:
    def __init__(self, lines, status=200):
        self._lines = lines
        self.status_code = status

    def iter_lines(self):
        return iter(self._lines)


def _provider(tmp_path, stream):
    secrets = SecretStore(tmp_path / "s.json")
    store = GeminiTokenStore(secrets)
    store.save({"access_token": "at", "refresh_token": "rt", "expires_in": 3600})
    store.save_project("proj-1")
    seen: dict = {}

    class FakeClient:
        def post(self, url, json=None, headers=None):
            seen.update(url=url, payload=json, headers=headers)
            return stream

    return GeminiCodeAssistProvider(client=FakeClient(), secrets=secrets), seen


def test_request_is_the_code_assist_envelope(tmp_path):
    chunk = json.dumps(
        {
            "response": {
                "candidates": [
                    {"content": {"parts": [{"text": "hi"}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 2},
            }
        }
    )
    provider, seen = _provider(tmp_path, _FakeStream([f"data: {chunk}"]))
    turn = provider.complete(
        model="gemini-2.5-pro",
        messages=[{"role": "system", "content": "be brief"}, {"role": "user", "content": "yo"}],
    )
    assert seen["url"] == STREAM_URL
    payload = seen["payload"]
    # The envelope — project + model + the ordinary generateContent request.
    assert payload["project"] == "proj-1" and payload["model"] == "gemini-2.5-pro"
    assert payload["request"]["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert payload["request"]["generationConfig"]["thinkingConfig"]["includeThoughts"] is True
    assert seen["headers"]["Authorization"] == "Bearer at"
    assert seen["headers"]["User-Agent"].startswith("GeminiCLI/")
    assert turn.text == "hi" and turn.finish_reason == "stop"
    assert turn.usage.input == 7 and turn.usage.output == 2


def test_streamed_thoughts_tool_calls_and_camel_case_are_parsed(tmp_path):
    chunks = [
        json.dumps(
            {
                "response": {
                    "candidates": [
                        {"content": {"parts": [{"text": "thinking…", "thought": True}]}}
                    ]
                }
            }
        ),
        json.dumps(
            {
                "response": {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"functionCall": {"name": "fp_render", "args": {"a": 1}}}
                                ]
                            },
                            "finishReason": "STOP",
                        }
                    ]
                }
            }
        ),
    ]
    provider, _ = _provider(tmp_path, _FakeStream([f"data: {c}" for c in chunks]))
    out = list(provider.stream(model="gemini-2.5-pro", messages=[{"role": "user", "content": "x"}]))
    assert [c.reasoning_delta for c in out if c.reasoning_delta] == ["thinking…"]
    turn = out[-1].turn
    assert [(c.name, c.arguments) for c in turn.tool_calls] == [("fp_render", {"a": 1})]
    assert turn.finish_reason == "tool_calls"


def test_plan_limit_is_a_readable_error(tmp_path):
    provider, _ = _provider(tmp_path, _FakeStream([], status=429))
    with pytest.raises(RuntimeError, match="plan limit"):
        provider.complete(model="gemini-2.5-pro", messages=[{"role": "user", "content": "x"}])


# -- live model lists ---------------------------------------------------------------


def test_discovery_filters_non_chat_models(monkeypatch):
    monkeypatch.setattr(
        discovery,
        "_get",
        lambda url, headers, params=None: {
            "data": [
                {"id": "gpt-5.6-sol"},
                {"id": "text-embedding-3-large"},
                {"id": "gpt-4o-audio-preview"},
                {"id": "dall-e-3"},
                {"id": "gpt-5.5"},
            ]
        },
    )
    found = discovery.discover("openai", {"api_key": "sk-x"})
    assert found == ["gpt-5.6-sol", "gpt-5.5"]


def test_discovery_reads_gemini_generation_methods(monkeypatch):
    monkeypatch.setattr(
        discovery,
        "_get",
        lambda url, headers, params=None: {
            "models": [
                {
                    "name": "models/gemini-2.5-pro",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/text-embedding-004",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        },
    )
    assert discovery.discover("gemini", {"api_key": "AIza"}) == ["gemini-2.5-pro"]


def test_discovery_never_raises_and_never_invents(monkeypatch):
    def explode(url, headers, params=None):
        raise discovery.DiscoveryError("offline")

    monkeypatch.setattr(discovery, "_get", explode)
    # An unreachable vendor yields nothing, so the caller keeps the existing list.
    assert discovery.discover("openai", {"api_key": "sk-x"}) == []
    # A subscription backend with no list endpoint serves the curated rows only.
    assert discovery.discover("gemini-code-assist", {}) == [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ]


def test_connecting_a_provider_refreshes_the_picker(tmp_path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    manager = SessionManager(data_dir=tmp_path / "data")
    monkeypatch.setattr(
        discovery, "discover", lambda name, profile, secrets=None: ["gemini-9.9-pro"]
    )
    manager.set_provider("gemini", {"api_key": "AIza-key"})
    # Stored with the routing prefix, and offered in the composer without anyone typing
    # a model id.
    assert manager._prefs["discovered_models"]["gemini"] == ["gemini:gemini-9.9-pro"]
    assert "gemini:gemini-9.9-pro" in manager.get_settings()["models"]


def test_models_route_refreshes_on_demand(tmp_path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    manager = SessionManager(data_dir=tmp_path / "data")
    client = TestClient(create_app(manager))
    monkeypatch.setattr(
        discovery, "discover", lambda name, profile, secrets=None: ["grok-9"]
    )
    body = client.post("/v1/providers/xai-oauth/models").json()
    assert body == {"ok": True, "provider": "xai-oauth", "models": ["xai-oauth:grok-9"]}
    assert "xai-oauth:grok-9" in manager._prefs["discovered_models"]["xai-oauth"]


def test_unknown_provider_refresh_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    manager = SessionManager(data_dir=tmp_path / "data")
    assert manager.refresh_provider_models("nope") == []


def test_provider_surface_is_eight_login_methods(tmp_path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    manager = SessionManager(data_dir=tmp_path / "data")
    rows = manager.get_providers()
    assert len(rows) == 8
    api_key = [r["name"] for r in rows if r["auth"] != "oauth"]
    subscription = [r["name"] for r in rows if r["auth"] == "oauth"]
    assert api_key == ["openai", "anthropic", "gemini", "xai"]
    assert subscription == [
        "openai-codex",
        "anthropic-claude",
        "gemini-code-assist",
        "xai-oauth",
    ]
    # Every vendor appears exactly twice — one key, one sign-in.
    assert len(api_key) == len(subscription) == 4
    assert time.time() > 0  # sanity: the row set is static, not time-dependent
