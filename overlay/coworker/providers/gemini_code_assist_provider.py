"""`gemini-code-assist` provider — Gemini models through a Google subscription.

The Code Assist backend speaks the same `generateContent` payload as the public Gemini
API, wrapped in an envelope that names the account's project:

    POST https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse
    {"project": "<id>", "model": "<id>", "request": {contents, systemInstruction, …}}

So every converter and the response parser are inherited from `gemini_provider`; this
module only translates the SDK-shaped request into the REST envelope, streams SSE with the
OAuth bearer, and wraps each chunk so the shared parser can read it. There is no Google SDK
client here — the SDK has no Code Assist transport.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Iterator, Optional

from .base import AssistantTurn, ModelCapabilities, ProviderClient, StreamChunk, ToolCall
from .capabilities import capabilities_for
from .gemini_auth import (
    CODE_ASSIST_ENDPOINT,
    PLAN_LIMIT_ERROR,
    GeminiSignInRequired,
    GeminiTokenStore,
    client_headers,
)
from .gemini_provider import (
    _map_finish,
    _parse_candidate,
    _signature_extras,
    _usage_from,
    convert_messages,
    convert_tools,
)

STREAM_URL = f"{CODE_ASSIST_ENDPOINT}/v1internal:streamGenerateContent?alt=sse"
# The SDK config keys `gemini_provider` produces, in the REST spelling this endpoint wants.
_WIRE_KEYS = {
    "max_output_tokens": "maxOutputTokens",
    "stop_sequences": "stopSequences",
    "temperature": "temperature",
    "top_p": "topP",
    "top_k": "topK",
}
_THINKING_KEYS = {"include_thoughts": "includeThoughts", "thinking_budget": "thinkingBudget"}
# REST field → the snake_case attribute `gemini_provider`'s parser reads.
_PARSE_KEYS = {
    "functionCall": "function_call",
    "finishReason": "finish_reason",
    "usageMetadata": "usage_metadata",
    "thoughtSignature": "thought_signature",
    "promptTokenCount": "prompt_token_count",
    "candidatesTokenCount": "candidates_token_count",
    "cachedContentTokenCount": "cached_content_token_count",
    "thoughtsTokenCount": "thoughts_token_count",
    "totalTokenCount": "total_token_count",
}
# Values that are payload, not wire structure, and must stay plain data.
_RAW_KEYS = frozenset({"args"})


def _namespace(value: Any) -> Any:
    """Wrap decoded JSON so the shared parser's attribute access works unchanged.

    `_parse_candidate` reads `.candidates[0].content.parts[*].text/.function_call/.thought`;
    the REST body carries the same shape in camelCase, so the keys are re-spelled here
    rather than forking the parser.
    """
    if isinstance(value, dict):
        return SimpleNamespace(
            **{
                _PARSE_KEYS.get(key, key): (
                    # Tool-call arguments are opaque payload, not wire structure: the
                    # parser hands them to the engine as a dict.
                    item if key in _RAW_KEYS else _namespace(item)
                )
                for key, item in value.items()
            }
        )
    if isinstance(value, list):
        return [_namespace(item) for item in value]
    return value


class GeminiCodeAssistProvider(ProviderClient):
    def __init__(
        self,
        client: Any = None,
        *,
        secrets: Any = None,
        default_model: str = "gemini-2.5-pro",
    ):
        # `client` is a test seam: any object with `post(url, json=..., headers=...)`
        # returning an SSE-capable response stands in for httpx.
        self._client = client
        self._store = GeminiTokenStore(secrets)
        self.default_model = default_model

    # -- request shaping -------------------------------------------------------
    def _envelope(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        settings: dict[str, Any],
        project: str,
    ) -> dict[str, Any]:
        system, contents = convert_messages(messages)
        if "max_tokens" in settings and "max_output_tokens" not in settings:
            settings["max_output_tokens"] = settings["max_tokens"]
        if "stop" in settings and "stop_sequences" not in settings:
            stop = settings["stop"]
            settings["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)
        generation = {
            wire: settings[key] for key, wire in _WIRE_KEYS.items() if key in settings
        }
        request: dict[str, Any] = {"contents": contents}
        if system:
            request["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            converted = convert_tools(tools)
            if converted:
                request["tools"] = converted
        # Thought summaries: same opt-in as the API-key path, REST spelling.
        generation["thinkingConfig"] = {_THINKING_KEYS["include_thoughts"]: True}
        request["generationConfig"] = generation
        return {"project": project, "model": model, "request": request}

    # -- transport -------------------------------------------------------------
    def _post(self, model: str, payload: dict[str, Any]) -> Any:
        token, project = self._store.access_token()
        payload["project"] = project
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            **client_headers(model),
        }
        if self._client is not None:
            return self._client.post(STREAM_URL, json=payload, headers=headers)
        import httpx

        return httpx.stream(
            "POST", STREAM_URL, json=payload, headers=headers, timeout=600.0
        )

    def _events(self, model: str, payload: dict[str, Any]) -> Iterator[Any]:
        """Decoded SSE chunks. Each `data:` line is `{"response": GenerateContentResponse}`."""
        response = self._post(model, payload)
        context = response if hasattr(response, "__enter__") else None
        if context is not None:
            response = context.__enter__()
        try:
            status = getattr(response, "status_code", 200)
            if status == 429:
                raise RuntimeError(PLAN_LIMIT_ERROR)
            if status in (401, 403):
                # The bearer or the project grant died; a refresh is the only fix, and a
                # rejected refresh surfaces as sign-in-required rather than a retry loop.
                self._store.refresh()
                raise GeminiSignInRequired(
                    "Google rejected the subscription credential — sign in again in "
                    "Settings ▸ Models."
                )
            if status >= 300:
                raise RuntimeError(f"Google Code Assist returned HTTP {status}.")
            for line in response.iter_lines():
                text = line.decode("utf-8") if isinstance(line, bytes) else line
                if not text or not text.startswith("data:"):
                    continue
                body = text[5:].strip()
                if not body or body == "[DONE]":
                    continue
                try:
                    decoded = json.loads(body)
                except ValueError:
                    continue
                inner = decoded.get("response") if isinstance(decoded, dict) else None
                yield _namespace(inner if inner is not None else decoded)
        finally:
            if context is not None:
                context.__exit__(None, None, None)

    # -- ProviderClient --------------------------------------------------------
    def capabilities(self, model: str) -> ModelCapabilities:
        return capabilities_for(model)

    def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ) -> Iterator[StreamChunk]:
        payload = self._envelope(
            model=model, messages=messages, tools=tools, settings=settings, project=""
        )
        texts: list[str] = []
        thoughts: list[str] = []
        calls: list[ToolCall] = []
        call_sigs: list[Optional[str]] = []
        text_sig: Optional[str] = None
        finish: Optional[str] = None
        usage = None
        for chunk in self._events(model, payload):
            chunk_usage = _usage_from(getattr(chunk, "usage_metadata", None))
            if chunk_usage is not None:
                usage = chunk_usage
            parsed = _parse_candidate(chunk)
            for thought in parsed.thoughts:
                thoughts.append(thought)
                yield StreamChunk(reasoning_delta=thought)
            for text in parsed.texts:
                texts.append(text)
                yield StreamChunk(text_delta=text)
            calls.extend(parsed.calls)
            call_sigs.extend(parsed.call_sigs)
            if parsed.text_sig:
                text_sig = parsed.text_sig
            if parsed.finish:
                finish = parsed.finish
        tool_calls = [
            ToolCall(id=f"call_{i}", name=c.name, arguments=c.arguments)
            for i, c in enumerate(calls)
        ]
        yield StreamChunk(
            turn=AssistantTurn(
                text="".join(texts) or None,
                tool_calls=tool_calls,
                finish_reason=_map_finish(finish, bool(tool_calls)),
                reasoning="".join(thoughts) or None,
                extras=_signature_extras(text_sig, call_sigs),
                usage=usage,
            )
        )

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ) -> AssistantTurn:
        # The endpoint only serves the streaming method — aggregate it.
        turn: Optional[AssistantTurn] = None
        for chunk in self.stream(
            model=model, messages=messages, tools=tools, **settings
        ):
            if chunk.turn is not None:
                turn = chunk.turn
        return turn if turn is not None else AssistantTurn()
