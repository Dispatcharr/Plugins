"""Events: start time and date parsing from stream names, titles, template
rendering, and grouping into Entries split by active / stale / deferred.
No Django imports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone as dt_timezone

from .config import TEMPLATE_TOKEN_RE
from .names import (
    Entry,
    clean_event_title,
    name_matches,
    normalize_key,
    order_streams,
    pick_display_name,
)


@dataclass(frozen=True)
class EventEntries:
    active: tuple  # Entry, chronological; channels to exist now
    stale: tuple  # Entry; started more than stale_hours ago
    deferred: tuple  # Entry; starts beyond lead_hours, not created yet


def build_event_entries(stream_lists, config, now_local):
    """Turn one list of streams per event pool into EventEntries per pool.

    All pools are parsed together because the day/month order of ambiguous
    dates ('05/11') is inferred from the whole batch. `now_local` must be an
    aware datetime in server-local time; today and the local timezone come
    from it.
    """
    today = now_local.date()
    local_tz = now_local.tzinfo
    parsed_lists = []
    ambiguous_pairs = []
    for streams in stream_lists:
        parsed = []
        for stream in streams:
            if name_matches(stream.name, config.event_not):
                continue
            time_part, date_part, spans = extract_event_fields(stream.name, config.event_regex)
            parsed.append((stream, time_part, date_part, spans))
            if date_part is not None and date_part[0] == "ambig":
                ambiguous_pairs.append((date_part[1], date_part[2]))
        parsed_lists.append(parsed)
    order = infer_day_month_order(ambiguous_pairs, today)
    stale_cutoff = now_local - timedelta(hours=config.stale_hours)
    return tuple(
        _group_events(parsed, config, order, now_local, today, local_tz, stale_cutoff)
        for parsed in parsed_lists
    )


def _group_events(parsed, config, order, now_local, today, local_tz, stale_cutoff):
    groups = {}
    for stream, time_part, date_part, spans in parsed:
        as_is = name_matches(stream.name, config.event_as_is)
        if as_is:
            cleaned = stream.name.strip()
        else:
            cleaned = clean_event_title(_blank_spans(stream.name, spans), config.event_token_re)
        start_dt = None
        date_key = ""
        if time_part is not None:
            event_date = resolve_event_date(date_part, order, today) or today
            start_dt = build_start_dt(time_part, event_date, local_tz)
            date_key = event_date.isoformat()
        key = normalize_key(cleaned) + "|" + date_key
        group = groups.get(key)
        if group is None:
            group = groups[key] = {
                "streams": [], "variants": [], "start_dt": start_dt, "as_is": as_is,
            }
        group["streams"].append(stream)
        group["variants"].append(cleaned)
        if start_dt is not None and (group["start_dt"] is None or start_dt < group["start_dt"]):
            group["start_dt"] = start_dt

    entries = []
    for key, group in groups.items():
        display = pick_display_name(group["variants"])
        if group["as_is"]:
            name = display
        else:
            name = render_event_name(config.template, display, group["start_dt"])
        entries.append(Entry(
            key=key,
            name=name,
            name_keys=(name,),
            streams=order_streams(group["streams"], config.cap_rank),
            start_dt=group["start_dt"],
        ))
    entries.sort(
        key=lambda e: (e.start_dt is None, e.start_dt.timestamp() if e.start_dt else 0.0, e.name)
    )
    active, stale, deferred = [], [], []
    for entry in entries:
        start_dt = entry.start_dt
        if start_dt is not None and start_dt <= stale_cutoff:
            stale.append(entry)
        elif (
            start_dt is not None
            and config.lead_hours > 0
            and start_dt - now_local > timedelta(hours=config.lead_hours)
        ):
            deferred.append(entry)
        else:
            active.append(entry)
    return EventEntries(active=tuple(active), stale=tuple(stale), deferred=tuple(deferred))


# ---------------------------------------------------------------------------
# Start time/date extraction from stream names
# ---------------------------------------------------------------------------

# Timezone abbreviations -> UTC offset in minutes. Taken literally (EST is
# always -5): abbreviations carry no DST rules. Unknown ones are ignored.
_TZ_OFFSETS = {
    "UTC": 0, "GMT": 0,
    "EST": -300, "EDT": -240,
    "CST": -360, "CDT": -300,
    "MST": -420, "MDT": -360,
    "PST": -480, "PDT": -420,
    "WET": 0, "WEST": 60, "BST": 60,
    "CET": 60, "CEST": 120,
    "EET": 120, "EEST": 180,
    "AEST": 600, "AEDT": 660,
}

_TIME_RE = re.compile(
    r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)"  # HH:MM
    r"(?:\s*([AaPp]\.?[Mm]\.?)(?![A-Za-z]))?"   # optional AM/PM
    r"(?:\s+([A-Za-z]{2,4}))?"                  # optional TZ abbreviation
)
_ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
# D/M, M/D, D.M, optionally with a 2- or 4-digit year (same separator).
_NUM_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})([/.])(\d{1,2})(?:\2(\d{2,4}))?(?!\d)")


def _time_from_match(m):
    """((hour24, minute, utc_offset_minutes_or_None), span_end) for a _TIME_RE match.

    AM/PM applies only to 1-12 hours; the TZ word counts only when it is a
    known abbreviation - otherwise it is title text and stays in the name.
    """
    hh = int(m.group(1))
    mm = int(m.group(2))
    end = m.end(2)
    ampm = m.group(3)
    if ampm and 1 <= hh <= 12:
        end = m.end(3)
        if ampm[0].lower() == "p" and hh != 12:
            hh += 12
        elif ampm[0].lower() == "a" and hh == 12:
            hh = 0
    offset = None
    tz = m.group(4)
    if tz is not None:
        offset = _TZ_OFFSETS.get(tz.upper())
        if offset is not None:
            end = m.end(4)
    return (hh, mm, offset), end


def _parse_time_text(text):
    m = _TIME_RE.search(text)
    return _time_from_match(m)[0] if m else None


def _parse_date_text(text):
    """("iso", y, m, d) or ("ambig", first, second, year_or_None) or None."""
    m = _ISO_DATE_RE.search(text)
    if m:
        return ("iso", int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _NUM_DATE_RE.search(text)
    if m:
        year = int(m.group(4)) if m.group(4) else None
        return ("ambig", int(m.group(1)), int(m.group(3)), year)
    return None


def extract_event_fields(name, custom_regex=None):
    """Extract raw start time and date tokens from a stream name.

    Tries the custom regex first (named groups 'time', optional 'date');
    falls back to the built-in scan when it is absent or does not match.

    Returns (time_part, date_part, spans):
        time_part: (hour24, minute, utc_offset_minutes_or_None) or None
        date_part: as _parse_date_text, or None
        spans: character ranges in `name` holding the matched time/date text
    """
    if custom_regex is not None:
        m = custom_regex.search(name)
        if m:
            groups = m.groupdict()
            time_text = groups.get("time")
            time_part = _parse_time_text(time_text) if time_text else None
            if time_part is not None:
                spans = [m.span("time")]
                date_part = None
                date_text = groups.get("date")
                if date_text:
                    date_part = _parse_date_text(date_text)
                    if date_part is not None:
                        spans.append(m.span("date"))
                return time_part, date_part, spans

    spans = []
    time_part = None
    m = _TIME_RE.search(name)
    if m:
        time_part, end = _time_from_match(m)
        spans.append((m.start(), end))
    date_part = None
    iso = _ISO_DATE_RE.search(name)
    num = _NUM_DATE_RE.search(name)
    if iso and (num is None or iso.start() < num.start()):
        date_part = ("iso", int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        spans.append(iso.span())
    elif num:
        year = int(num.group(4)) if num.group(4) else None
        date_part = ("ambig", int(num.group(1)), int(num.group(3)), year)
        spans.append(num.span())
    return time_part, date_part, spans


def _blank_spans(name, spans):
    chars = list(name)
    for start, end in spans:
        for i in range(start, min(end, len(chars))):
            chars[i] = " "
    return "".join(chars)


def infer_day_month_order(pairs, today):
    """Decide D/M vs M/D for the whole batch of (first, second) date pairs.

    A value over 12 in one position fixes that position as the day; failing
    that, the position that more often equals the current month (give or take
    a couple of days) is the month. Undecidable falls back to day-first.
    """
    first_over = any(a > 12 for a, _b in pairs)
    second_over = any(b > 12 for _a, b in pairs)
    if first_over != second_over:
        return "dm" if first_over else "md"
    if first_over:  # conflicting evidence
        return "dm"
    near_months = {(today + timedelta(days=o)).month for o in (-1, 0, 1, 2)}
    first_hits = sum(1 for a, _b in pairs if a in near_months)
    second_hits = sum(1 for _a, b in pairs if b in near_months)
    if first_hits != second_hits:
        return "md" if first_hits > second_hits else "dm"
    return "dm"


def resolve_event_date(date_part, order, today):
    """date_part -> datetime.date, or None when it cannot be a real date.

    Yearless dates get the year that puts them nearest to today, so '31/12'
    parsed on Jan 2 means four days ago, not eleven months ahead.
    """
    if date_part is None:
        return today
    if date_part[0] == "iso":
        _kind, year, month, day = date_part
        try:
            return date(year, month, day)
        except ValueError:
            return None
    _kind, first, second, year = date_part
    day, month = (first, second) if order == "dm" else (second, first)
    if month > 12 and day <= 12:
        day, month = month, day
    if year is not None:
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    best = None
    for candidate_year in (today.year - 1, today.year, today.year + 1):
        try:
            candidate = date(candidate_year, month, day)
        except ValueError:
            continue
        delta = abs((candidate - today).days)
        if best is None or delta < best[0]:
            best = (delta, candidate)
    return best[1] if best else None


def build_start_dt(time_part, event_date, local_tz):
    """Aware start datetime in server-local time."""
    hh, mm, offset = time_part
    naive = datetime.combine(event_date, dt_time(hh, mm))
    if offset is None:
        return naive.replace(tzinfo=local_tz)
    return naive.replace(tzinfo=dt_timezone(timedelta(minutes=offset))).astimezone(local_tz)


# ---------------------------------------------------------------------------
# Event channel names - template rendering
# ---------------------------------------------------------------------------

_WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def render_event_name(template, title, start_dt):
    """Fill the name template. Without a start time, date/time tokens vanish
    and the name collapses to the title. Unknown tokens stay as written."""

    def _sub(m):
        token, arg = m.group(1), m.group(2)
        if token == "title":
            return title
        if start_dt is None:
            return ""
        if token == "time":
            return start_dt.strftime("%H:%M")
        if token == "time12":
            return start_dt.strftime("%I:%M %p").lstrip("0")
        if token == "date":
            return f"{start_dt.day:02d}/{start_dt.month:02d}"
        if token == "usdate":
            return f"{start_dt.month:02d}/{start_dt.day:02d}"
        if token == "isodate":
            return start_dt.strftime("%Y-%m-%d")
        if token == "weekday":
            names = _WEEKDAY_NAMES
            if arg:
                custom = [p.strip() for p in arg.split(",")]
                if len(custom) == 7 and all(custom):
                    names = custom
            return names[start_dt.weekday()]
        return m.group(0)

    rendered = TEMPLATE_TOKEN_RE.sub(_sub, template)
    return re.sub(r"\s+", " ", rendered).strip() or title
