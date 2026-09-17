"""Small, strict serialization and filesystem boundary shared by FP tools."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any

MAX_INPUT = 2 * 1024 * 1024
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

class ConflictError(ValueError):
    """The source revision changed; inspect again rather than overwriting it."""


def valid_name(name: str) -> str:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("Invalid infographic name; use 1-64 ASCII letters, digits, dot, dash, underscore")
    return name


def _pairs(items):
    out = {}
    for k, v in items:
        if k in out:
            raise ValueError(f"Duplicate JSON key: {k}")
        out[k] = v
    return out


def validate_json(value: Any, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("JSON nesting exceeds 64")
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str) or k in {"__proto__", "prototype", "constructor"}:
                raise ValueError("Unsafe JSON key")
            validate_json(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > 10000:
            raise ValueError("JSON array exceeds 10000 elements")
        for v in value:
            validate_json(v, depth + 1)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value) or abs(value) > 9007199254740991:
            raise ValueError("Non-finite or unsafe JSON number; large identifiers must be strings")
    elif value is not None and not isinstance(value, (str, bool)):
        raise ValueError("Unsupported JSON value")


def dumps(value: Any) -> str:
    validate_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def loads(raw: str, limit: int = MAX_INPUT) -> Any:
    if len(raw.encode("utf-8")) > limit:
        raise ValueError("JSON size limit exceeded")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
        validate_json(value)
        return value
    except (RecursionError, UnicodeError) as e:
        raise ValueError("Invalid or excessively nested JSON") from e


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_path(root: Path, relative: str, *, create_parent: bool = False) -> Path:
    """Reject traversal and existing symlinks. Not an OS sandbox for hostile local users."""
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Path must stay inside the granted workspace")
    cur = root
    for part in rel.parts:
        cur = cur / part
        if cur.is_symlink():
            raise ValueError(f"Symlink is not allowed in FP storage: {cur.name}")
    if create_parent:
        cur.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not cur.resolve().is_relative_to(root):
        raise ValueError("Path escapes workspace")
    return cur


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".fp-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        # Persist the rename on POSIX filesystems, including APFS.
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def pointer_get(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("Bindings require an RFC 6901 JSON pointer")
    cur = value
    for raw in pointer[1:].split("/"):
        if re.search(r"~(?![01])", raw):
            raise ValueError("Invalid JSON pointer escape")
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", key):
                raise ValueError("Invalid array index")
            cur = cur[int(key)]
        else:
            cur = cur[key]
    return cur
