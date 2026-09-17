"""`anthropic-claude` provider — Claude models through a Pro/Max subscription.

The wire is the same Messages API the API-key path speaks, so every converter, thinking
rule and stream parser is inherited from `AnthropicProvider`. This subclass changes only
what the subscription credential requires:

  - `Authorization: Bearer <oauth token>` instead of `x-api-key`, plus the CLI
    fingerprint headers and beta set the subscription backend gates on.
  - `system[0]` is the CLI identity block. The backend rejects OAuth inference that
    does not carry it; the session's real system prompt follows it.
  - Custom tool names are prefixed with `_` on the wire and stripped on the way back.
    Without this, a tool whose name collides with an Anthropic server tool
    (`web_search`, `web_fetch`, `computer`, …) is rejected — and this build ships
    exactly those names.
  - 401 → one refresh-and-retry; 429 → the plan's usage window as a readable error.
"""

from __future__ import annotations

from itertools import chain
from typing import Any, Iterator, Optional

from .anthropic_auth import (
    CLIENT_USER_AGENT,
    OAUTH_BETA,
    PLAN_LIMIT_ERROR,
    ClaudeTokenStore,
)
from .anthropic_provider import AnthropicProvider
from .base import AssistantTurn, StreamChunk

# The identity block Claude Code's runtime sends as the first system block.
CLI_SYSTEM_INSTRUCTION = "You are Claude Code, Anthropic's official CLI for Claude."
# Wire prefix isolating our tools from the backend's built-ins. One prefix, applied
# once on send and removed once on receive.
TOOL_PREFIX = "_"
# Betas the subscription backend expects from the CLI client. `context-1m-2025-08-07`
# is deliberately absent: subscription credentials have no long-context credit, so
# advertising it hard-429s every request on a 1M model.
CLIENT_BETAS = (
    "claude-code-20250219",
    OAUTH_BETA,
    "interleaved-thinking-2025-05-14",
    "context-management-2025-06-27",
    "prompt-caching-scope-2026-01-05",
)


def _status_code(exc: Exception) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def encode_tool_name(name: str) -> str:
    return TOOL_PREFIX + name


def decode_tool_name(name: str) -> str:
    return name[len(TOOL_PREFIX) :] if name.startswith(TOOL_PREFIX) else name


class ClaudeSubscriptionProvider(AnthropicProvider):
    def __init__(
        self,
        client: Any = None,
        *,
        secrets: Any = None,
        default_model: str = "claude-opus-4-8",
        thinking_budget: Optional[int] = None,
    ):
        super().__init__(
            client=client,
            default_model=default_model,
            secrets=secrets,
            thinking_budget=thinking_budget,
        )
        self._store = ClaudeTokenStore(secrets)
        self._client_token: Optional[str] = None
        self._injected = client is not None

    # -- credential -------------------------------------------------------------
    def _ensure_client(self) -> Any:
        if self._injected:
            return self._client
        # The bearer is short-lived: fetch per call (the store refreshes near expiry)
        # and rebuild the SDK client whenever the token rotated.
        token = self._store.access_token()
        if self._client is None or token != self._client_token:
            from anthropic import Anthropic

            self._client = Anthropic(
                auth_token=token,
                default_headers={
                    "anthropic-beta": ",".join(CLIENT_BETAS),
                    "User-Agent": CLIENT_USER_AGENT,
                    "x-app": "cli",
                },
            )
            self._client_token = token
        return self._client

    # -- request shaping --------------------------------------------------------
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
        kwargs["system"] = self._system_blocks(kwargs.get("system"))
        if kwargs.get("tools"):
            kwargs["tools"] = [
                {**tool, "name": encode_tool_name(tool.get("name") or "")}
                for tool in kwargs["tools"]
            ]
        # Replayed history must name the tools the way the wire saw them, or the
        # backend sees a tool_use for a tool that was never declared.
        self._encode_history_tool_names(kwargs.get("messages") or [])
        return kwargs

    @staticmethod
    def _system_blocks(system: Any) -> list[dict[str, Any]]:
        """CLI identity block first, then the session's own system prompt."""
        head: dict[str, Any] = {"type": "text", "text": CLI_SYSTEM_INSTRUCTION}
        if not system:
            return [head]
        if isinstance(system, str):
            return [head, {"type": "text", "text": system}]
        blocks = list(system)
        if blocks and blocks[0].get("text") == CLI_SYSTEM_INSTRUCTION:
            return blocks
        return [head, *blocks]

    @staticmethod
    def _encode_history_tool_names(messages: list[dict[str, Any]]) -> None:
        for message in messages:
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    block["name"] = encode_tool_name(block.get("name") or "")

    @staticmethod
    def _decode_turn(turn: AssistantTurn) -> AssistantTurn:
        for call in turn.tool_calls or []:
            call.name = decode_tool_name(call.name)
        return turn

    # -- calls ------------------------------------------------------------------
    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ) -> AssistantTurn:
        try:
            turn = super().complete(
                model=model, messages=messages, tools=tools, **settings
            )
        except Exception as exc:
            self._reauth_or_raise(exc)
            turn = super().complete(
                model=model, messages=messages, tools=tools, **settings
            )
        return self._decode_turn(turn)

    def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        **settings: Any,
    ) -> Iterator[StreamChunk]:
        def run() -> Iterator[StreamChunk]:
            return super(ClaudeSubscriptionProvider, self).stream(
                model=model, messages=messages, tools=tools, **settings
            )

        try:
            chunks = run()
            first = next(chunks, None)
        except Exception as exc:
            # Only the pre-stream failure is safely retryable: once text has been
            # yielded, a retry would duplicate it.
            self._reauth_or_raise(exc)
            chunks = run()
            first = next(chunks, None)
        if first is None:
            return
        # chain, not unpacking: unpacking would drain the whole stream before the
        # first token reached the caller.
        for chunk in chain((first,), chunks):
            if chunk.turn is not None:
                self._decode_turn(chunk.turn)
            yield chunk

    def _reauth_or_raise(self, exc: Exception) -> None:
        """401 → force a refresh so the caller can retry once. 429 → the plan window."""
        status = _status_code(exc)
        if status == 429:
            raise RuntimeError(PLAN_LIMIT_ERROR) from exc
        if status != 401 or self._injected:
            raise exc
        # A rejected refresh token raises ClaudeSignInRequired out of the store.
        self._store.refresh()
        self._client = None
        self._client_token = None
