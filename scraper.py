"""
Events Radar scraper.

    python scraper.py            # full refresh -> events.db + docs/events.json
    python scraper.py --quick    # skip firm-page scans and curated live-checks
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import config
import curated
import dates
import db
import sources

log = logging.getLogger("scraper")
_RX = lambda pats: re.compile("|".join(pats), re.I)
TRACKS = [(n, _RX(p)) for n, p in config.TRACK_RULES]
HUBS = [(n, _RX(p)) for n, p in config.HUBS]
ELIG = [(n, _RX(p)) for n, p in config.ELIGIBILITY_RULES]
EXCL = _RX(config.EXCLUDE)
_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "ref", "fbclid", "src"}
DOCS = Path(__file__).parent / "docs"


def canonical_url(url: str) -> str:
    p = urlparse(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if k not in _TRACKING]
    return urlunparse((p.scheme.lower() or "https", p.netloc.lower().replace("www.", ""), p.path.rstrip("/"), "", urlencode(q), ""))


def event_id(url: str, title: str = "") -> str:
    return hashlib.sha1(canonical_url(url).encode()).hexdigest()[:16]


def tracks_for(title: str, desc: str, given: list | None) -> list[str]:
    if given:
        return given
    hay = f"{title} {desc}"
    found = [n for n, rx in TRACKS if rx.search(hay)]
    return found or ["SWE"]


def hubs_for(location: str, fmt: str) -> list[str]:
    loc = location or ""
    found = [n for n, rx in HUBS if rx.search(loc)]
    if fmt == "Virtual" and "Online" not in found:
        found.append("Online")
    specific = [h for h in found if h not in ("Other US", "Online")]
    if specific and "Other US" in found:
        found.remove("Other US")
    return found or ["Not specified"]


def eligibility_for(text: str, given: str) -> str:
    if given and given.strip() and given.strip() != "?":
        return given.strip()[:80]
    hay = text
    found = [n for n, rx in ELIG if rx.search(hay)]
    if "Freshman" in found or "Sophomore" in found:
        return "Underclassmen" if {"Freshman", "Sophomore"} <= set(found) else found[0]
    for n in ("Junior", "PhD", "Undergrad", "Students"):
        if n in found:
            return n
    return given.strip() or "Anyone"


def normalise(raw: dict) -> dict | None:
    title = (raw.get("title") or "").strip()
    url = raw.get("url")
    if not title or not url or not url.startswith("http") or EXCL.search(title):
        return None
    if not raw.get("type"):
        return None
    desc = raw.get("description") or ""
    fmt = raw.get("format") or "Varies"
    loc = raw.get("location") or ""
    if fmt == "Varies" and loc:
        fmt = "Virtual" if re.search(r"online|virtual", loc, re.I) else "In person"
    start = raw.get("start")
    today = date.today()
    # Past confirmed events (ended > 14 days ago) are dropped
    end = raw.get("end") or start
    if end and date.fromisoformat(end) < today.replace(day=1) and raw.get("confidence") == "confirmed":
        return None
    approx = False
    if not start and raw.get("month"):
        start = dates.next_occurrence(raw["month"], today).isoformat()
        end = None
        approx = True
    return {
        "id": event_id(url),
        "title": title,
        "host": (raw.get("host") or "").strip() or "Unknown",
        "url": url,
        "type": raw["type"],
        "tracks": tracks_for(title, desc, raw.get("tracks")),
        "format": fmt,
        "location": loc,
        "hubs": hubs_for(loc, fmt),
        "start": start,
        "end": end,
        "deadline": raw.get("deadline"),
        "approx": approx,                       # start is a "typical month", not a real date
        "confidence": raw.get("confidence", "typical"),
        "eligibility": eligibility_for(f"{title} {desc}", raw.get("eligibility") or ""),
        "when": raw.get("when") or "",
        "description": desc[:600],
        "source": raw.get("source", ""),
        "source_type": raw.get("source_type", ""),
        "page_status": raw.get("page_status", ""),
    }


def collect(quick: bool = False, progress=None) -> tuple[list[dict], dict]:
    tasks = [("Devpost", sources.fetch_devpost, ()), ("MLH", sources.fetch_mlh, ())]
    for name, url, kind in config.GITHUB_LISTS:
        tasks.append((f"GitHub · {name}", sources.fetch_github_list, (name, url, kind)))
    if quick:
        tasks.append(("Curated (no live check)", lambda: [dict(i, confidence="typical") for i in _curated_plain()], ()))
    else:
        for host, url in config.FIRM_EVENT_PAGES:
            tasks.append((f"Careers page · {host}", sources.scan_page_for_events, (host, url)))
        for item in curated.CURATED:
            tasks.append((f"Curated · {item['title'][:40]}", lambda it=item: [sources.check_curated(it)], ()))

    events, stats, done = {}, {}, 0
    rank = {"Company site": 0, "Curated": 1, "Hackathon platform": 2, "GitHub list": 3}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(fn, *args): label for label, fn, args in tasks}
        for fut in as_completed(futs):
            label = futs[fut]
            done += 1
            try:
                raws = fut.result()
            except Exception as e:
                log.warning("%s crashed: %s", label, e)
                raws = []
            kept = 0
            for raw in raws:
                ev = normalise(raw)
                if not ev:
                    continue
                prev = events.get(ev["id"])
                if prev is None or rank.get(ev["source_type"], 9) < rank.get(prev["source_type"], 9):
                    if prev:
                        ev["deadline"] = ev["deadline"] or prev["deadline"]
                        if not ev["start"] or ev["approx"]:
                            ev["start"], ev["end"], ev["approx"] = prev["start"], prev["end"], prev["approx"]
                    events[ev["id"]] = ev
                kept += 1
            stats[label] = {"fetched": len(raws), "kept": kept}
            if progress:
                progress(done, len(tasks), label, len(raws), kept)
    return list(events.values()), stats


def _curated_plain():
    for it in curated.CURATED:
        yield dict(title=it["title"], host=it["host"], url=it["url"], type=it["type"], tracks=it.get("tracks"),
                   format=it.get("format", "Varies"), location=it.get("location", ""), start=it.get("start"),
                   end=it.get("end"), deadline=it.get("deadline"), eligibility=it.get("eligibility", ""),
                   description=it.get("when", ""), source="Curated", source_type="Curated",
                   month=it.get("month", 0), when=it.get("when", ""))


def export_json(summary: dict | None = None) -> Path:
    DOCS.mkdir(exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "last_run": summary or db.last_run(),
               "events": db.all_events(include_inactive=True)}
    out = DOCS / "events.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return out


def refresh(quick: bool = False, progress=None) -> dict:
    events, stats = collect(quick=quick, progress=progress)
    summary = db.upsert_events(events, full_run=not quick)
    summary["sources"] = stats
    summary["ran_at"] = datetime.now(timezone.utc).isoformat()
    db.record_run(summary)
    export_json({k: v for k, v in summary.items() if k != "sources"})
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO if a.v else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    def prog(done, total, label, fetched, kept):
        print(f"[{done:>2}/{total}] {label:<55} {fetched:>4} fetched  {kept:>3} kept", file=sys.stderr)

    s = refresh(quick=a.quick, progress=prog)
    print(f"\n{s['total_active']} active events ({s['new']} new, {s['closed']} closed this run)")
