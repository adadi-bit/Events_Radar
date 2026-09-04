"""SQLite state for Events Radar: events (first_seen / last_seen / active) + run log."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "events.db"
COLS = ["id", "title", "host", "url", "type", "tracks", "format", "location", "hubs", "start", "end",
        "deadline", "approx", "confidence", "eligibility", "when_text", "description", "source",
        "source_type", "page_status", "first_seen", "last_seen", "active"]
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS events ({", ".join(c + (" TEXT PRIMARY KEY" if c == "id" else " TEXT") for c in COLS)});
CREATE TABLE IF NOT EXISTS runs (ran_at TEXT, summary TEXT);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    if set(COLS) - cols:
        conn.executescript("DROP TABLE events;" + SCHEMA)
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(ev: dict, first_seen: str, now: str, active: int) -> tuple:
    return (ev["id"], ev["title"], ev["host"], ev["url"], ev["type"], json.dumps(ev["tracks"]), ev["format"],
            ev["location"], json.dumps(ev["hubs"]), ev["start"], ev["end"], ev["deadline"], int(bool(ev["approx"])),
            ev["confidence"], ev["eligibility"], ev["when"], ev["description"], ev["source"], ev["source_type"],
            ev["page_status"], first_seen, now, active)


def upsert_events(events: list[dict], full_run: bool = True) -> dict:
    conn = connect()
    now = _now()
    existing = {r["id"]: r for r in conn.execute("SELECT id, first_seen, active FROM events")}
    new = 0
    seen = set()
    for ev in events:
        seen.add(ev["id"])
        prev = existing.get(ev["id"])
        first = prev["first_seen"] if prev else now
        if prev is None:
            new += 1
        conn.execute(f"INSERT OR REPLACE INTO events VALUES ({','.join('?' * len(COLS))})", _row(ev, first, now, 1))
    closed = 0
    if full_run:
        for r in conn.execute("SELECT id FROM events WHERE active='1'").fetchall():
            if r["id"] not in seen:
                conn.execute("UPDATE events SET active='0' WHERE id=?", (r["id"],))
                closed += 1
    # prune long-dead / long-past rows
    cutoff = date.today().replace(day=1).isoformat()
    conn.execute("DELETE FROM events WHERE active='0' AND (end IS NULL OR end < ?)", (cutoff,))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM events WHERE active='1'").fetchone()[0]
    conn.close()
    return {"new": new, "closed": closed, "total_active": total, "scraped": len(events)}


def record_run(summary: dict):
    conn = connect()
    conn.execute("INSERT INTO runs VALUES (?,?)", (summary["ran_at"], json.dumps(summary)))
    conn.commit()
    conn.close()


def last_run():
    conn = connect()
    r = conn.execute("SELECT summary FROM runs ORDER BY ran_at DESC LIMIT 1").fetchone()
    conn.close()
    return json.loads(r[0]) if r else None


def all_events(include_inactive: bool = False) -> list[dict]:
    conn = connect()
    q = "SELECT * FROM events" + ("" if include_inactive else " WHERE active='1'")
    rows = conn.execute(q).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["tracks"] = json.loads(d["tracks"] or "[]")
        d["hubs"] = json.loads(d["hubs"] or "[]")
        d["approx"] = d["approx"] in ("1", 1, True)
        d["active"] = d["active"] in ("1", 1, True)
        d["when"] = d.pop("when_text") or ""
        out.append(d)
    return out
