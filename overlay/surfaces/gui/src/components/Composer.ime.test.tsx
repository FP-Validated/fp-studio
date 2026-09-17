// Korean (and Japanese/Chinese) input: the Enter that COMMITS a composing syllable
// must not send the message. Pressing Enter mid-composition used to fire onSend with
// a half-typed word — the single most visible Korean-input defect in a chat composer.
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Composer } from "./Composer";

const props = (extra: Partial<Parameters<typeof Composer>[0]> = {}) => ({
  mode: "interactive",
  model: "gpt-5.6-sol",
  running: false,
  connected: true,
  sessionId: "s1",
  onSend: vi.fn(),
  onInterrupt: vi.fn(),
  onModeChange: vi.fn(),
  onModelChange: vi.fn(),
  ...extra,
});

// Query the control, not its copy: the placeholder is product wording and has
// already been rewritten once (FP Studio says "agent", never "coworker").
const box = () => screen.getByRole("textbox");

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("composer IME composition", () => {
  it("does not send while the IME reports an active composition", () => {
    const p = props();
    render(<Composer {...p} />);
    fireEvent.change(box(), { target: { value: "안녕하세" } });
    // Chromium/Gecko path: the committing keydown carries isComposing.
    fireEvent.keyDown(box(), { key: "Enter", isComposing: true });
    expect(p.onSend).not.toHaveBeenCalled();
  });

  it("does not send on the WebKit commit keydown after compositionend", () => {
    const p = props();
    render(<Composer {...p} />);
    fireEvent.change(box(), { target: { value: "한글" } });
    // macOS WebKit (the Tauri webview) fires compositionend BEFORE the keydown and
    // leaves isComposing false on it — the tracked flag is what catches this.
    fireEvent.compositionStart(box());
    fireEvent.compositionEnd(box());
    fireEvent.keyDown(box(), { key: "Enter" });
    expect(p.onSend).not.toHaveBeenCalled();
  });

  it("sends on a plain Enter once composition has settled", async () => {
    const p = props();
    render(<Composer {...p} />);
    fireEvent.change(box(), { target: { value: "한글 입력" } });
    fireEvent.compositionStart(box());
    fireEvent.compositionEnd(box());
    // The guard releases one tick later; the next Enter is a real send.
    // (`Promise.withResolvers` is past this project's TS lib target.)
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 1));
    });
    fireEvent.keyDown(box(), { key: "Enter" });
    expect(p.onSend).toHaveBeenCalledTimes(1);
    expect(p.onSend).toHaveBeenCalledWith("한글 입력", [], undefined);
  });

  it("still treats Shift+Enter as a newline, not a send", () => {
    const p = props();
    render(<Composer {...p} />);
    fireEvent.change(box(), { target: { value: "줄바꿈" } });
    fireEvent.keyDown(box(), { key: "Enter", shiftKey: true });
    expect(p.onSend).not.toHaveBeenCalled();
  });
});
