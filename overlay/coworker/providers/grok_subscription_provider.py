"""`xai-oauth` provider — Grok models through a SuperGrok / X Premium+ subscription.

xAI serves the OpenAI **Responses** wire at `https://api.x.ai/v1`, so conversion and
stream parsing are inherited from `OpenAIResponsesProvider`. This subclass changes only
what the subscription credential and xAI's endpoint require:

  - The bearer is the device-flow OAuth token from `xai_auth`, not an API key, and the
    SDK client is rebuilt whenever the token rotates.
  - `include: ["reasoning.encrypted_content"]` is dropped: xAI does not serve encrypted
    reasoning, and replaying the sidecar makes it 400.
  - `reasoning.effort` only rides for models that accept it; on the rest xAI answers
    HTTP 400 rather than ignoring the field.
  - 401 → one refresh-and-retry; 429 → the plan's usage window as a readable error.
"""

from __future__ import annotations

from typing import Any, Optional

from .openai_responses import OpenAIResponsesProvider
from .xai_auth import PLAN_LIMIT_ERROR, XaiTokenStore

BASE_URL = "https://api.x.ai/v1"
# Models xAI accepts `reasoning.effort` on. Everything else 400s on the field, so it is
# removed rather than mapped (checked against the vendor's curated OAuth catalog).
_REASONING_EFFORT_MODELS = (
    "grok-3-mini",
    "grok-4.3",
    "grok-4.5",
    "grok-4.6",
    "grok-4.20-multi-agent",
)
# xAI's effort vocabulary has no "minimal" tier.
_EFFORT_ALIASES = {"minimal": "low"}


def _status_code(exc: Exception) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def supports_reasoning_effort(model: str) -> bool:
    return model.startswith(_REASONING_EFFORT_MODELS)


class GrokSubscriptionProvider(OpenAIResponsesProvider):
    def __init__(
        self,
        client: Any = None,
        *,
        secrets: Any = None,
        default_model: str = "grok-4.6",
    ):
        super().__init__(
            client=client,
            default_model=default_model,
            base_url=BASE_URL,
            # xAI rejects `reasoning.summary`; the display falls back to text only.
            reasoning_summary=False,
        )
        self._store = XaiTokenStore(secrets)
        self._client_token: Optional[str] = None
        self._injected = client is not None

    def _ensure_client(self) -> Any:
        if self._injected:
            return self._client
        token = self._store.access_token()
        if self._client is None or token != self._client_token:
            from openai import OpenAI

            self._client = OpenAI(api_key=token, base_url=BASE_URL)
            self._client_token = token
        return self._client

    def _request_kwargs(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        kwargs = super()._request_kwargs(
            model=model, messages=messages, tools=tools, settings=settings
        )
        kwargs.pop("include", None)
        effort = settings.get("reasoning_effort")
        if isinstance(effort, str) and effort and supports_reasoning_effort(model):
            kwargs["reasoning"] = {
                **kwargs.get("reasoning", {}),
                "effort": _EFFORT_ALIASES.get(effort, effort),
            }
        else:
            kwargs.pop("reasoning", None)
        return kwargs

    def _create(self, client: Any, kwargs: dict[str, Any]) -> Any:
        try:
            return super()._create(client, kwargs)
        except Exception as exc:
            status = _status_code(exc)
            if status == 401 and not self._injected:
                # The bearer died mid-flight: force one refresh and retry once. A
                # rejected refresh raises XaiSignInRequired out of the store.
                self._store.refresh()
                self._client = None
                self._client_token = None
                return super()._create(self._ensure_client(), kwargs)
            if status == 429:
                raise RuntimeError(PLAN_LIMIT_ERROR) from exc
            raise
