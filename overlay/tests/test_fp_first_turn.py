"""The first message of a session is the one that carries the source and the declaration.

The GUI opens the session socket before it knows the folder, so `?workspace=` is empty on
exactly that connection. FP read the query parameter, found nothing, and skipped capture —
so an attached image was never a captured source and "화이트 다크 두 버전" was never a
declaration. Two recorded conversations paid for that: twelve `fp_inspect` calls hunting for
an image the user had already handed over, four `ask_user` rounds about an appearance the
user had stated in their first sentence, and a light version that was refused every time.

The workspace now comes from the manager — the same resolution the engine binds — so a
capture happens wherever the turn is about to run.
"""

from __future__ import annotations

import base64
import struct
import sys
import zlib

from fastapi.testclient import TestClient

from coworker.fp.store import Store
from coworker.server import SessionManager, create_app

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from test_server import ScriptedProvider, _text  # noqa: E402


def _png(width: int = 480, height: int = 160) -> bytes:
    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + b"\x9a" * (width * 3) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def _client(workspace, turns):
    manager = SessionManager(workspace=workspace, provider=ScriptedProvider(turns))
    return TestClient(create_app(manager))


def test_the_first_message_is_captured_when_the_socket_names_no_workspace(tmp_path):
    """`?workspace=` empty is the normal shape of a brand-new session, not an error."""
    data_url = "data:image/png;base64," + base64.b64encode(_png()).decode()
    client = _client(tmp_path, [_text("looking at it")])

    with client.websocket_connect("/ws/session/first?workspace=&agent=cowork") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({
            "type": "user_message",
            "text": "화이트 다크 2가지 버전으로 각각 인포그래픽 만들어줘",
            "attachments": [{"kind": "image", "name": "table.png",
                             "mime": "image/png", "data_url": data_url}],
        })
        while ws.receive_json()["type"] != "turn_done":
            pass

    store = Store(tmp_path)
    captured = [row for row in store.sources() if row.get("kind") == "image"]
    assert [row["locator"] for row in captured] == ["attachment:table.png"]
    assert (tmp_path / captured[0]["file"]).read_bytes() == _png()
    # And the appearance the user stated in that same sentence is on the record, so the
    # render gate opens without a question.
    assert store.appearance()["mode"] == "both"
    assert store.appearance()["channel"] == "message"


def test_an_answer_records_against_the_same_workspace(tmp_path):
    """The ask channel resolved the workspace the same broken way; both paths move together."""
    from coworker.fp.reference import record_appearance

    store = Store(tmp_path)
    assert record_appearance(store, "Both", "ask", "Light or dark?")["mode"] == "both"
    assert store.appearance()["channel"] == "ask"
