"""A screenshot is not a million tokens.

An attached image travels as a `data:` URL, and the compaction trigger estimated context
by dividing the serialized messages by four. A 1.1 MB screenshot is ~1.47 M base64
characters, so the estimate read ~367 k tokens against a 102,400 trigger: a session
compacted itself on its FIRST turn, three and a half times "over" a window it was using
about 1,200 tokens of. The boundary landed right after the user's only message, so the
summary — which can only write "[image]" — became the model's memory of the picture it had
been asked to redraw. It then worked blind: transcribing figures it could no longer read
and guessing which of the day's screenshots the user had meant. Every later turn carrying
an image did it again, which is why the trim notice kept reappearing.

Three things are fixed here and pinned below: attachments are priced at what a vision call
actually costs, a token cap the user typed is no longer inert for a model the matrix does
not know, and the newest reference images cross the boundary with the compacted block.
"""

from __future__ import annotations

import base64
import sys

from coworker import compaction as C

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from test_compaction_engine import (  # noqa: E402
    CompactingProvider,
    collect,
    long_history,
    make_engine,
)

# The size that produced the report: a Retina screenshot of a table.
SCREENSHOT_BYTES = 1_100_000


def _data_url(size: int = SCREENSHOT_BYTES) -> str:
    return "data:image/png;base64," + base64.b64encode(b"\x89PNG" + b"\x00" * size).decode()


def _turn_with_image(text: str = "요청 인포그래픽 1 — 다크버전으로") -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": _data_url()}},
        ],
    }


def test_an_attached_screenshot_does_not_trigger_compaction_on_the_first_turn():
    messages = [{"role": "system", "content": "be helpful"}, _turn_with_image()]
    estimate = C.estimate_tokens(messages)
    assert estimate < C.trigger_tokens(None), (
        f"a brand-new session estimated {estimate:,} tokens against a "
        f"{C.trigger_tokens(None):,} trigger"
    )
    assert not C.should_compact(estimate, None)


def test_the_estimate_prices_an_image_like_a_vision_call_not_like_its_base64():
    """The payload is transport. What the model is billed is the image."""
    one = C.estimate_tokens([_turn_with_image("")])
    assert C.IMAGE_TOKENS <= one < C.IMAGE_TOKENS + 200
    # Twice the bytes is the same picture, so it is the same price.
    big = [{"role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": _data_url(4_000_000)}}]}]
    assert C.estimate_tokens(big) == C.estimate_tokens(
        [{"role": "user", "content": [{"type": "image_url",
                                       "image_url": {"url": _data_url(100_000)}}]}]
    )
    # Text in the same message is still counted as text.
    assert C.estimate_tokens([_turn_with_image("t" * 4_000)]) >= one + 1_000


def test_a_pdf_attachment_is_priced_too():
    pdf = {
        "role": "user",
        "content": [
            {"type": "file", "file": {"filename": "deck.pdf",
                                      "file_data": "data:application/pdf;base64,"
                                      + base64.b64encode(b"%PDF" + b"0" * 900_000).decode()}}
        ],
    }
    assert C.estimate_tokens([pdf]) < C.FILE_TOKENS + 200


def test_a_typed_token_cap_is_not_inert_for_a_model_the_matrix_does_not_know():
    """With no verified window the default 128 k is a guess, and `min` can only lower a
    guess. A cap the user typed in Settings has to be able to raise it."""
    assert C.trigger_tokens(None, cap_tokens=1_000_000) == int(
        0.8 * C.DEFAULT_CONTEXT_WINDOW
    )
    assert C.trigger_tokens(None, cap_tokens=1_000_000, cap_explicit=True) == 1_000_000
    # A verified window still wins: the cap only ever lowers it.
    assert C.trigger_tokens(200_000, cap_tokens=1_000_000, cap_explicit=True) == 160_000


def test_the_reference_image_crosses_the_compaction_boundary():
    messages = [
        {"role": "system", "content": "be helpful"},
        _turn_with_image(),
        {"role": "assistant", "content": "표를 읽었습니다."},
        {"role": "user", "content": "다크로 다시"},
        {"role": "assistant", "content": "발행했습니다."},
    ]
    state = C.CompactionState(
        boundary_index=3, summary_text="(요약)", working_state="",
        user_messages=["요청"], user_messages_dropped=0, created_at=0.0, model_used="m",
    )
    out = C.apply_to_outbound(messages, state)
    parts = out[1]["content"]
    assert isinstance(parts, list)
    assert "<compacted-history>" in parts[0]["text"]
    images = [p for p in parts if p.get("type") == "image_url"]
    assert [p["image_url"]["url"] for p in images] == [_data_url()]


def test_only_the_newest_reference_images_are_carried():
    messages = [{"role": "system", "content": "s"}]
    for i in range(4):
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": f"turn {i}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,i{i}"}}],
        })
        messages.append({"role": "assistant", "content": f"a{i}"})
    messages.append({"role": "user", "content": "now"})
    carried = C.carried_images(messages, len(messages) - 1)
    assert [p["image_url"]["url"] for p in carried] == [
        "data:image/png;base64,i2",
        "data:image/png;base64,i3",
    ]
    assert len(carried) == C.CARRY_IMAGES


def test_a_text_only_compaction_still_sends_a_plain_string_block():
    """No attachment, no parts list — the block stays byte-identical for prompt caching."""
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "older"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "newest"},
    ]
    state = C.CompactionState(
        boundary_index=3, summary_text="(요약)", working_state="",
        user_messages=["older"], user_messages_dropped=0, created_at=0.0, model_used="m",
    )
    out = C.apply_to_outbound(messages, state)
    assert isinstance(out[1]["content"], str)


def test_the_summarizer_failure_reason_reaches_the_user(tmp_path, monkeypatch):
    """Retry or Trim was asked with the cause swallowed by a bare `except Exception`, and
    nothing was written anywhere. The reason now rides on the notice and the prompt."""
    import coworker.engine as engine_module

    monkeypatch.setattr(engine_module, "_COMPACTION_RETRY_DELAY", 0)

    class RateLimited(CompactingProvider):
        def complete(self, *, model, messages, tools=None, **settings):
            if messages and "compacting an AI coworker" in str(messages[0].get("content", "")):
                self.summary_calls.append({"model": model, "messages": messages})
                raise RuntimeError("Error 429: rate_limit_error — usage window exhausted")
            return super().complete(model=model, messages=messages, tools=tools, **settings)

    from coworker.providers import AssistantTurn

    provider = RateLimited([AssistantTurn(text="done", finish_reason="stop")])
    engine = make_engine(tmp_path, provider, messages=long_history(), cap=400)
    events = collect(engine)

    compacted = [e for e in events if e.type.name == "COMPACTED"]
    assert compacted, "the trim fallback still has to report itself"
    text = compacted[0].data["text"]
    assert "trimmed" in text.lower() and "429" in text
    assert len(provider.summary_calls) == 2  # first try + the one backed-off retry


def test_the_retry_waits_before_trying_again(tmp_path, monkeypatch):
    """An instant retry lands inside the same rate-limit window, which is how one failure
    became two and put the dialog on screen."""
    import coworker.engine as engine_module

    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(engine_module.asyncio, "sleep", _sleep)
    from coworker.providers import AssistantTurn

    provider = CompactingProvider(
        [AssistantTurn(text="done", finish_reason="stop")], summary_fails=99
    )
    engine = make_engine(tmp_path, provider, messages=long_history(), cap=400)
    collect(engine)
    assert slept == [engine_module._COMPACTION_RETRY_DELAY]


def test_the_engine_still_sends_the_image_after_it_compacts(tmp_path):
    """End of the chain: what the next model call actually receives. Before this, the
    attachment was gone from the outbound view and the model was left with the word
    "[image]" as its memory of the source it had been asked to redraw."""
    from coworker.providers import AssistantTurn, ModelCapabilities

    class SeeingProvider(CompactingProvider):
        def capabilities(self, model):
            return ModelCapabilities(vision=True)

    history = long_history()
    history.insert(1, _turn_with_image())
    provider = SeeingProvider([AssistantTurn(text="done", finish_reason="stop")])
    engine = make_engine(tmp_path, provider, messages=history, cap=400)
    collect(engine)

    assert engine.compaction_state is not None
    out = engine._outbound_messages()
    urls = [
        part["image_url"]["url"]
        for msg in out
        if isinstance(msg.get("content"), list)
        for part in msg["content"]
        if isinstance(part, dict) and part.get("type") == "image_url"
    ]
    assert urls == [_data_url()]
    # The summary is still there — the image rides WITH the block, not instead of it.
    assert "<compacted-history>" in str(out[1]["content"])
