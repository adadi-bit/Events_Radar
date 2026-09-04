"""Date-range parsing for messy event text."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_M = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_D = r"(\d{1,2})(?:st|nd|rd|th)?"
_Y = r"(20\d\d)"
DASH = r"\s*(?:-|–|—|to|through|until)\s*"

# "Sep 11 - 13, 2026" / "Sep 11-13" / "Jul 31 - Oct 01, 2026" / "October 27–30, 2026" / "March 24th - March 28th, 2025"
RANGE_RE = re.compile(
    rf"\b{_M}\.?\s+{_D},?(?:\s+{_Y})?{DASH}(?:{_M}\.?\s+)?{_D},?(?:\s+{_Y})?\b", re.I)
# "September 16, 2026" / "Sep 16 2026" / "16 September 2026"
SINGLE_RE = re.compile(rf"\b{_M}\.?\s+{_D},?\s+{_Y}\b|\b{_D}\s+{_M}\.?,?\s+{_Y}\b", re.I)
ISO_RE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)(?!\d)")
MD_RE = re.compile(rf"\b{_M}\.?\s+{_D}\b(?![\s,]*20\d\d)", re.I)
DEADLINE_WORDS = re.compile(r"(deadline|apply by|applications? (?:close|due|are due)|register by|registration (?:closes|deadline)|due date|closes? on|submit by|last day to)", re.I)


def _mk(y, m, d) -> date | None:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _mon(s: str) -> int:
    return MONTHS[s[:3].lower()]


def parse_range(text: str, default_year: int | None = None) -> tuple[date | None, date | None]:
    """Return (start, end) from the first date range / single date found in text."""
    if not text:
        return None, None
    t = text.replace(" ", " ")
    m = RANGE_RE.search(t)
    if m:
        m1, d1, y1, m2, d2, y2 = m.groups()
        y2 = y2 or y1 or (str(default_year) if default_year else None)
        y1 = y1 or y2
        if not y1:
            return None, None
        mm2 = _mon(m2) if m2 else _mon(m1)
        s, e = _mk(y1, _mon(m1), d1), _mk(y2, mm2, d2)
        if s and e and e < s:            # "Dec 30 - Jan 2" without years
            e = _mk(int(y2) + 1, mm2, d2)
        return s, e
    m = SINGLE_RE.search(t)
    if m:
        g = m.groups()
        if g[0]:
            s = _mk(g[2], _mon(g[0]), g[1])
        else:
            s = _mk(g[5], _mon(g[4]), g[3])
        return s, s
    m = ISO_RE.search(t)
    if m:
        s = _mk(*m.groups())
        return s, s
    if default_year:
        m = MD_RE.search(t)
        if m:
            s = _mk(default_year, _mon(m.group(1)), m.group(2))
            return s, s
    return None, None


def all_dates(text: str, default_year: int | None = None) -> list[tuple[date, date, int]]:
    """Every (start, end, char_offset) found in text — for page scanning."""
    out = []
    t = (text or "").replace(" ", " ")
    for rx in (RANGE_RE, SINGLE_RE, ISO_RE, MD_RE):
        for m in rx.finditer(t):
            s, e = parse_range(m.group(0), default_year)
            if s:
                out.append((s, e or s, m.start()))
    out.sort(key=lambda x: x[2])
    return out


def find_deadline(text: str, default_year: int | None = None) -> date | None:
    """A date that appears within ~90 chars after a deadline-ish phrase."""
    t = (text or "").replace(" ", " ")
    for m in DEADLINE_WORDS.finditer(t):
        window = t[m.end(): m.end() + 90]
        s, _ = parse_range(window, default_year)
        if s:
            return s
    return None


def plausible(d: date | None, today: date | None = None) -> bool:
    today = today or date.today()
    return bool(d) and (today - timedelta(days=45)) <= d <= (today + timedelta(days=420))


def next_occurrence(month: int, today: date | None = None) -> date:
    """First day of the next `month` (this year if still ahead, else next)."""
    today = today or date.today()
    y = today.year if month >= today.month else today.year + 1
    return date(y, month, 1)
