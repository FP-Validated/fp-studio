"""Live model lists, so nobody types a model id by hand.

Each vendor publishes the models a credential may use; this module asks, filters the
result down to text/chat-capable ids, and returns them sorted newest-looking first. The
manager calls it whenever a provider is connected or verified and merges the result into
the picker.

Design constraints that shaped it:

  - **Never fatal.** A vendor outage, an offline machine or an endpoint that answers 404
    must not break connecting a provider. Every helper raises `DiscoveryError`, and the
    caller keeps the curated matrix.
  - **No guessing.** Subscription backends that publish no list endpoint (the ChatGPT
    plan backend, Cloud Code Assist) return the curated matrix rows for that provider
    instead of a fabricated list.
  - **Chat only.** Embedding, audio, image and moderation ids are filtered out — they
    cannot serve a turn, and a picker full of them is worse than a short list.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

TIMEOUT = 15.0
# Ids that cannot serve a conversational turn.
_EXCLUDE = re.compile(
    r"(embed|embedding|tts|whisper|audio|transcribe|speech|image|dall-e|imagen|"
    r"moderation|rerank|guard|vision-encoder|veo|imagine|stt|voice)",
    re.IGNORECASE,
)
# Ids the vendor lists but that are not usable as a normal chat model.
_EXCLUDE_EXACT = frozenset({"gpt-3.5-turbo-instruct", "davinci-002", "babbage-002"})


class DiscoveryError(RuntimeError):
    """The vendor could not be asked, or answered with something unusable."""


def _get(url: str, headers: dict[str, str], params: Optional[dict[str, str]] = None) -> Any:
    import httpx

    try:
        response = httpx.get(url, headers=headers, params=params, timeout=TIMEOUT)
    except Exception as exc:
        raise DiscoveryError(
            f"Couldn't reach the model list ({exc.__class__.__name__})."
        ) from exc
    if response.status_code >= 300:
        raise DiscoveryError(f"The model list returned HTTP {response.status_code}.")
    try:
        return response.json()
    except ValueError as exc:
        raise DiscoveryError("The model list was not JSON.") from exc


def _usable(model_id: str) -> bool:
    model_id = model_id.strip()
    if not model_id or model_id in _EXCLUDE_EXACT:
        return False
    return not _EXCLUDE.search(model_id)


def _openai_shaped(body: Any) -> list[str]:
    """`{"data": [{"id": …}]}` — OpenAI, xAI and every compatible endpoint."""
    rows = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise DiscoveryError("The model list had no `data` array.")
    return [
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and row.get("id") and _usable(str(row["id"]))
    ]


def _anthropic_models(key: str, *, oauth: bool = False) -> list[str]:
    headers = {"anthropic-version": "2023-06-01", "Accept": "application/json"}
    if oauth:
        from .anthropic_auth import CLIENT_USER_AGENT, OAUTH_BETA

        headers.update(
            {
                "Authorization": f"Bearer {key}",
                "anthropic-beta": OAUTH_BETA,
                "User-Agent": CLIENT_USER_AGENT,
            }
        )
    else:
        headers["x-api-key"] = key
    body = _get("https://api.anthropic.com/v1/models", headers, {"limit": "100"})
    rows = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise DiscoveryError("The model list had no `data` array.")
    return [
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and row.get("id") and _usable(str(row["id"]))
    ]


def _gemini_models(key: str) -> list[str]:
    body = _get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        {"Accept": "application/json"},
        {"key": key, "pageSize": "200"},
    )
    rows = (body or {}).get("models") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise DiscoveryError("The model list had no `models` array.")
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # Only models that can actually answer a turn.
        methods = row.get("supportedGenerationMethods") or []
        if isinstance(methods, list) and methods and "generateContent" not in methods:
            continue
        name = str(row.get("name") or "")
        model_id = name.split("/")[-1]
        if model_id and _usable(model_id):
            out.append(model_id)
    return out


def _curated(provider: str) -> list[str]:
    """The vouched-for ids for a provider whose backend publishes no list."""
    from .matrix import models_for_provider

    return list(models_for_provider(provider))


def _key_for(name: str, profile: dict[str, Any], secrets: Any) -> str:
    import os

    from .registry import get_descriptor

    key = ((profile or {}).get("api_key") or "").strip()
    descriptor = get_descriptor(name)
    if not key and descriptor is not None and descriptor.env_key:
        key = (os.environ.get(descriptor.env_key) or "").strip()
    if not key:
        raise DiscoveryError(f"No {name} API key is configured.")
    return key


def list_models(name: str, profile: dict[str, Any], secrets: Any = None) -> list[str]:
    """The models this provider's CURRENT credential may use, as bare ids.

    Raises DiscoveryError; callers treat that as "keep what we have".
    """
    profile = profile or {}
    if name == "openai":
        base = (profile.get("base_url") or "https://api.openai.com/v1").strip().rstrip("/")
        key = _key_for(name, profile, secrets)
        return _openai_shaped(_get(f"{base}/models", {"Authorization": f"Bearer {key}"}))
    if name == "anthropic":
        return _anthropic_models(_key_for(name, profile, secrets))
    if name == "gemini":
        return _gemini_models(_key_for(name, profile, secrets))
    if name == "xai":
        base = (profile.get("base_url") or "https://api.x.ai/v1").strip().rstrip("/")
        key = _key_for(name, profile, secrets)
        return _openai_shaped(_get(f"{base}/models", {"Authorization": f"Bearer {key}"}))
    if name == "anthropic-claude":
        from .anthropic_auth import ClaudeTokenStore

        token = ClaudeTokenStore(secrets).access_token()
        try:
            return _anthropic_models(token, oauth=True)
        except DiscoveryError:
            # The subscription backend does not always serve /v1/models; the curated
            # rows are the vouched-for fallback, never an invented list.
            return _curated(name)
    if name == "xai-oauth":
        from .xai_auth import XaiTokenStore

        token = XaiTokenStore(secrets).access_token()
        try:
            return _openai_shaped(
                _get("https://api.x.ai/v1/models", {"Authorization": f"Bearer {token}"})
            )
        except DiscoveryError:
            return _curated(name)
    if name in ("openai-codex", "gemini-code-assist"):
        # Neither subscription backend publishes a model list. Curated rows only.
        return _curated(name)
    raise DiscoveryError(f"{name} has no model list endpoint.")


def discover(name: str, profile: dict[str, Any], secrets: Any = None) -> list[str]:
    """`list_models`, never raising: an empty list means "nothing new to offer"."""
    try:
        models = list_models(name, profile, secrets)
    except Exception as exc:
        logger.info("model discovery skipped for %s: %s", name, exc)
        return []
    # Stable order, newest-looking first: vendors list oldest-first as often as not, and
    # a version-descending list puts the model someone wants at the top.
    return sorted(dict.fromkeys(models), reverse=True)
