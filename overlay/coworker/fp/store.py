"""SQLite is authoritative; SVG/PNG/source files are repairable presentation caches.

Each visual revision commits its input, audit and BOTH artifact byte streams in one
transaction. Publication to filesystem aliases cannot be atomic as a pair; an explicit fp_repair
rebuilds them from the committed row after interruption. History never depends on aliases.
"""
from __future__ import annotations
import contextlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any
from .common import ConflictError, atomic_write, checked_path, digest, dumps, valid_name

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions (
 name TEXT NOT NULL, revision INTEGER NOT NULL, created_at REAL NOT NULL,
 source TEXT NOT NULL, svg BLOB NOT NULL, png BLOB NOT NULL, receipt TEXT NOT NULL,
 research_revision INTEGER NOT NULL, restored_from INTEGER,
 PRIMARY KEY(name, revision));
CREATE TABLE IF NOT EXISTS heads (name TEXT PRIMARY KEY, revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS research (
 name TEXT NOT NULL, revision INTEGER NOT NULL, created_at REAL NOT NULL,
 value TEXT NOT NULL, PRIMARY KEY(name,revision));
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, created_at REAL NOT NULL, locator TEXT NOT NULL,
 text TEXT NOT NULL, receipt TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS publications (
 name TEXT NOT NULL, revision INTEGER NOT NULL, research_revision INTEGER NOT NULL,
 created_at REAL NOT NULL, receipt TEXT NOT NULL,
 PRIMARY KEY(name,revision,research_revision));
"""

class Store:
    def __init__(self, workspace: str | Path):
        self.root = Path(workspace).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = checked_path(self.root, ".fpstudio/fp.sqlite3", create_parent=True)
        os.chmod(self.db.parent, 0o700)
        for suffix in ("-wal", "-shm", "-journal"):
            checked_path(self.root, ".fpstudio/fp.sqlite3" + suffix)
        with self.connect() as db:
            db.executescript(SCHEMA)
            schema = db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            if schema and schema[0] != "1":
                raise ValueError("Unsupported FP store version")
            db.execute("INSERT OR IGNORE INTO meta VALUES ('schema','1')")
        os.chmod(self.db, 0o600)

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def current_revision(self, name: str, db=None) -> int:
        valid_name(name)
        if db is None:
            with self.connect() as con:
                return self.current_revision(name, con)
        row = db.execute("SELECT revision FROM heads WHERE name=?", (name,)).fetchone()
        return row[0] if row else 0

    def research_current(self, name: str, db=None) -> dict:
        valid_name(name)
        if db is None:
            with self.connect() as con:
                return self.research_current(name, con)
        row = db.execute("SELECT revision,value FROM research WHERE name=? ORDER BY revision DESC LIMIT 1", (name,)).fetchone()
        return {"revision": row[0], "value": json.loads(row[1])} if row else {"revision": 0, "value": {}}

    def set_research(self, name: str, value: dict, expected: int) -> dict:
        raw = dumps(value)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cur = self.research_current(name, db)["revision"]
            if type(expected) is not int or cur != expected:
                raise ConflictError(f"Research revision changed: expected {expected}, current {cur}")
            db.execute("INSERT INTO research VALUES (?,?,?,?)", (name, cur+1, time.time(), raw))
        return {"revision": cur+1, "value": value}

    def capture(self, locator: str, text: str, metadata: dict) -> dict:
        if not text or len(text.encode('utf-8')) > 1024*1024:
            raise ValueError("Captured source is empty or exceeds 1 MiB")
        if len(locator) > 4000:
            raise ValueError("Source locator is too long")
        sha = digest(text.encode('utf-8'))
        sid = "src_" + digest((locator + "\n" + sha).encode('utf-8'))[:24]
        receipt = {**metadata, "id": sid, "locator": locator, "sha256": sha,
                   "captured_at": time.time(), "evidence_level": "captured-text-not-fact-verification"}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT receipt FROM sources WHERE id=?',(sid,)).fetchone()
            if existing:
                return json.loads(existing[0])
            used=db.execute('SELECT COALESCE(SUM(length(CAST(text AS BLOB))),0) FROM sources').fetchone()[0]
            if used+len(text.encode('utf-8'))>64*1024*1024:
                raise ValueError('Source archive exceeds 64 MiB; archive workspace before continuing')
            db.execute("INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?)", (sid,time.time(),locator,text,dumps(receipt)))
            row = db.execute("SELECT receipt FROM sources WHERE id=?", (sid,)).fetchone()
        return json.loads(row[0])

    def source(self, sid: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT text,receipt FROM sources WHERE id=?", (sid,)).fetchone()
        if not row:
            raise ValueError(f"Unknown captured source: {sid}")
        return {**json.loads(row[1]), "text": row[0]}

    def sources(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT receipt FROM sources ORDER BY created_at DESC LIMIT 100").fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, name: str, revision: int | None = None) -> dict | None:
        valid_name(name)
        with self.connect() as db:
            rev = revision if revision is not None else self.current_revision(name,db)
            row = db.execute("SELECT * FROM revisions WHERE name=? AND revision=?", (name,rev)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['input'] = json.loads(data.pop('source'))
        data['receipt'] = json.loads(data['receipt'])
        return data

    def commit(self, name: str, expected: int, source: dict, svg: bytes, png: bytes,
               receipt: dict, research_revision: int, *, restored_from=None, cancelled=None) -> dict:
        valid_name(name)
        raw = dumps(source)
        # Cap history rather than silently discard earlier work.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cur = self.current_revision(name,db)
            if type(expected) is not int or expected != cur:
                raise ConflictError(f"Document revision changed: expected {expected}, current {cur}")
            if self.research_current(name,db)["revision"] != research_revision:
                raise ConflictError("Research changed during render; inspect and retry")
            used = db.execute("SELECT COALESCE(SUM(length(svg)+length(png)+length(source)),0) FROM revisions").fetchone()[0]
            if used+len(svg)+len(png)+len(raw.encode()) > 512*1024*1024:
                raise ValueError("Workspace history exceeds 512 MiB; archive the workspace before continuing")
            if cancelled and cancelled():
                raise InterruptedError("Render cancelled; no new revision committed")
            rec = {**receipt, 'svg_sha256':digest(svg), 'png_sha256':digest(png),
                   'source_sha256':digest(raw.encode('utf-8')), 'status':'draft'}
            rev = cur+1
            db.execute("INSERT INTO revisions VALUES (?,?,?,?,?,?,?,?,?)", (name,rev,time.time(),raw,svg,png,dumps(rec),research_revision,restored_from))
            db.execute("INSERT INTO heads VALUES (?,?) ON CONFLICT(name) DO UPDATE SET revision=excluded.revision", (name,rev))
        cache_error = None
        try:
            self.materialize(name)
        except (OSError, ValueError) as e:
            cache_error = str(e)[:500]
        return {'revision':rev,'receipt':rec,'cache_error':cache_error}

    def materialize(self, name: str, revision: int | None = None) -> dict:
        # Serialize materializers with commits. Otherwise an older renderer can republish
        # its bytes AFTER a newer render finishes and leave the aliases silently stale.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rev = revision if revision is not None else self.current_revision(name,db)
            row = db.execute("SELECT * FROM revisions WHERE name=? AND revision=?", (name,rev)).fetchone()
            if row is None:
                raise ValueError("No such rendered revision")
            prefix = f"fp/{name}" if revision is None else f"fp/exports/{name}/r{rev:06d}"
            for ext in ('svg','png'):
                path = checked_path(self.root, f"{prefix}.{ext}", create_parent=True)
                data = bytes(row[ext])
                if not path.exists() or digest(path.read_bytes()) != digest(data):
                    atomic_write(path,data)
            source_path = checked_path(self.root, f"{prefix}.fp.json", create_parent=True)
            atomic_write(source_path,(row['source']+'\n').encode('utf-8'))
        return {'svg':prefix+'.svg','png':prefix+'.png','source':prefix+'.fp.json'}

    def history(self, name: str) -> list[dict]:
        valid_name(name)
        with self.connect() as db:
            rows = db.execute("SELECT revision,created_at,receipt,restored_from,research_revision FROM revisions WHERE name=? ORDER BY revision DESC LIMIT 100", (name,)).fetchall()
        return [{**dict(r),'receipt':json.loads(r['receipt'])} for r in rows]

    def publish(self, name: str, expected: int, expected_research: int, review: dict) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if self.current_revision(name,db) != expected or self.research_current(name,db)['revision'] != expected_research:
                raise ConflictError("Revision changed before publication")
            db.execute("INSERT OR IGNORE INTO publications VALUES (?,?,?,?,?)", (name,expected,expected_research,time.time(),dumps(review)))
        return self.materialize(name, expected)
