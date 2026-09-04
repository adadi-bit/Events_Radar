"""
Fetchers. Each returns raw event dicts:
  title, host, url, type, tracks(list|None), format, location, start, end, deadline
  (ISO str or None), eligibility, description, source, source_type, confidence
Fetchers never raise.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

import config
import dates

log = logging.getLogger("sources")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
for _p in ("https://", "http://"):
    S.mount(_p, requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20))
TIMEOUT = 20


def _get(url):
    r = S.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, date) else (d or None)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html or "", "html.parser").get_text(" ")).strip()


def _is_us_or_online(loc: str) -> bool:
    l = (loc or "").strip()
    low = l.lower()
    if not l or any(w in low for w in ("online", "virtual", "everywhere", "worldwide", "digital", "remote")):
        return True
    if "united states" in low or low.endswith(", us") or low.endswith(", usa"):
        return True
    m = re.search(r",\s*([A-Z]{2})\s*$", l)
    if m and m.group(1) in config.US_STATES:
        return True
    return any(s in low for s in config.US_STATE_NAMES)


# ------------------------------------------------------------------ Devpost
def fetch_devpost() -> list[dict]:
    out = []
    for page in range(1, config.DEVPOST_PAGES + 1):
        try:
            data = _get(config.DEVPOST_URL.format(page=page)).json()
        except Exception as e:
            log.warning("devpost page %d failed: %s", page, e)
            break
        hs = data.get("hackathons", [])
        if not hs:
            break
        for h in hs:
            loc = (h.get("displayed_location") or {}).get("location", "")
            if not _is_us_or_online(loc):
                continue
            s, e = dates.parse_range(h.get("submission_period_dates", ""), date.today().year)
            themes = ", ".join(t.get("name", "") for t in h.get("themes", []) or [])
            out.append(dict(
                title=h.get("title", "").strip(), host=h.get("organization_name") or "Devpost",
                url=h.get("url"), type="Hackathon", tracks=None,
                format="Virtual" if "online" in loc.lower() else "In person", location=loc,
                start=_iso(s), end=_iso(e), deadline=_iso(e),
                eligibility="Anyone" if not h.get("invite_only") else "Invite only",
                description=f"Themes: {themes}. Prizes: {h.get('prize_amount', '')}. {h.get('registrations_count', 0)} registered. Submissions {h.get('submission_period_dates', '')}.",
                source="Devpost", source_type="Hackathon platform", confidence="confirmed",
            ))
    return out


# ---------------------------------------------------------------------- MLH
def fetch_mlh() -> list[dict]:
    out = []
    for season in config.MLH_SEASONS:
        try:
            html = _get(config.MLH_URL.format(season=season)).text
        except Exception as e:
            log.warning("mlh %s failed: %s", season, e)
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select('a[itemtype*="Event"]'):
            meta = {m.get("itemprop"): m.get("content", "") for m in a.select("meta[itemprop]")}
            name = a.find(["h4", "h3"])
            title = name.get_text(" ").strip() if name else ""
            mode = meta.get("eventAttendanceMode", "")
            online = "Online" in mode or "Mixed" in mode
            city = ", ".join(filter(None, [meta.get("addressLocality"), meta.get("addressRegion")]))
            country = meta.get("addressCountry", "")
            if not (online or country in ("US", "USA", "United States")):
                continue
            loc = "Online" if online and not city else f"{city}, {country}".strip(", ")
            s = meta.get("startDate", "")[:10] or None
            e = meta.get("endDate", "")[:10] or None
            if not title or not meta.get("url"):
                continue
            out.append(dict(
                title=title, host="MLH member hackathon", url=meta["url"], type="Hackathon", tracks=["SWE"],
                format="Virtual" if online else "In person", location=loc, start=s, end=e, deadline=None,
                eligibility="Students", description="Major League Hacking season event.",
                source="MLH", source_type="Hackathon platform", confidence="confirmed",
            ))
    return out


# --------------------------------------------------------------- GitHub list
_SECTION_TYPE = {
    "fellowships": "Fellowship", "internship-matching fellowships": "Fellowship",
    "externships / insight series": "Insight program", "winternships": "Winternship",
    "special programs & resources": None, "internships": None,
}


def fetch_github_list(name: str, url: str, kind: str) -> list[dict]:
    try:
        md = _get(url).text
    except Exception as e:
        log.warning("github %s failed: %s", name, e)
        return []
    out, section, etype = [], "", None
    for line in md.splitlines():
        h = re.match(r"^##\s+(.+?)\s*$", line)
        if h:
            section = h.group(1).strip().lower()
            etype = _SECTION_TYPE.get(section, None)
            continue
        if etype is None or not line.startswith("|") or line.startswith("| Name") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        m = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", cells[0])
        if not m:
            continue
        title, link = m.group(1).strip(), m.group(2).strip()
        status, year, note = cells[1], cells[2], cells[3] if len(cells) > 3 else ""
        host = re.split(r"\s+(intern|fellow|program|summit|day|winternship|women)", title, 1, flags=re.I)[0].strip()
        out.append(dict(
            title=title, host=host or title, url=link, type=etype, tracks=None, format="Varies", location="",
            start=None, end=None, deadline=None, eligibility=year,
            description=f"{note} Status: {status}.".strip(),
            source=f"GitHub · {name}", source_type="GitHub list",
            confidence="typical", status_text=status,
        ))
    return out


# ------------------------------------------------------------ firm page scan
def scan_page_for_events(host: str, url: str) -> list[dict]:
    """Links that sit next to a plausible date on a firm's events page."""
    try:
        html = _get(url).text
    except Exception as e:
        log.warning("scan %s failed: %s", host, e)
        return []
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    yr = date.today().year
    for a in soup.find_all("a", href=True):
        title = re.sub(r"\s+", " ", a.get_text(" ")).strip()
        if not (6 <= len(title) <= 120) or re.match(r"^(learn more|read more|apply|register|view|see all|more)$", title, re.I):
            continue
        box = a.find_parent(["li", "article", "tr", "div"])
        txt = _text(str(box))[:600] if box else ""
        found = [x for x in dates.all_dates(txt, yr) if dates.plausible(x[0])]
        if not found:
            continue
        link = requests.compat.urljoin(url, a["href"])
        if link in seen or link.rstrip("/") == url.rstrip("/"):
            continue
        seen.add(link)
        s, e, _ = found[0]
        out.append(dict(
            title=title, host=host, url=link, type="Firm event", tracks=None, format="Varies",
            location=_loc_guess(txt), start=_iso(s), end=_iso(e), deadline=_iso(dates.find_deadline(txt, yr)),
            eligibility="Students", description=txt[:300],
            source=f"Careers page · {host}", source_type="Company site", confidence="confirmed",
        ))
    return out


_LOC = re.compile(r"(New York|NYC|Chicago|London|Austin|Boston|San Francisco|Bay Area|Miami|Houston|Greenwich|Stamford|"
                  r"Philadelphia|Bala Cynwyd|Pittsburgh|Seattle|Denver|Atlanta|Virtual|Online|Remote)", re.I)


def _loc_guess(text: str) -> str:
    seen = []
    for m in _LOC.finditer(text or ""):
        v = m.group(1)
        if v.lower() not in [x.lower() for x in seen]:
            seen.append(v)
    return " / ".join(seen)


# ------------------------------------------------------------- curated check
def check_curated(item: dict) -> dict:
    """Return the curated entry enriched with any dates/deadline stated on its page."""
    ev = dict(
        title=item["title"], host=item["host"], url=item["url"], type=item["type"], tracks=item.get("tracks"),
        format=item.get("format", "Varies"), location=item.get("location", ""),
        start=item.get("start"), end=item.get("end"), deadline=item.get("deadline"),
        eligibility=item.get("eligibility", ""), description=item.get("when", ""),
        source="Curated", source_type="Curated", confidence="confirmed" if item.get("start") else "typical",
        month=item.get("month", 0), when=item.get("when", ""),
    )
    try:
        html = _get(item["url"]).text
    except Exception as e:
        log.info("curated %s unreachable: %s", item["title"], e)
        ev["page_status"] = "unreachable"
        return ev
    txt = _text(html)
    ev["page_status"] = "ok"
    yr = date.today().year
    # deadline phrase wins
    dl = dates.find_deadline(txt, yr)
    if dates.plausible(dl):
        ev["deadline"] = _iso(dl)
    # a plausible future date range near the title's month
    if not ev["start"]:
        cands = [(s, e) for s, e, _ in dates.all_dates(txt, yr) if dates.plausible(s) and s >= date.today()]
        if item.get("month"):
            cands = [c for c in cands if abs(c[0].month - item["month"]) <= 1] or cands
        if cands:
            s, e = min(cands, key=lambda c: c[0])
            ev["start"], ev["end"], ev["confidence"] = _iso(s), _iso(e), "from page"
    snippet = re.search(r"(applications? (?:open|close|are open|will open)[^.]{0,120}\.)", txt, re.I)
    if snippet:
        ev["description"] = f"{ev['description']} · Page says: “{snippet.group(1).strip()}”"
    return ev
