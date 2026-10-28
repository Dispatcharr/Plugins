"""
Automap Channelarr - Dispatcharr plugin

Deterministic, rule-based channel mapper: maps M3U groups to channel-number
blocks, replacing the built-in automapper (auto_channel_sync).

Streams from all M3U accounts in a configured group are pooled, grouped by a
normalized channel name (country prefix, quality markers, punctuation and
whitespace removed), and each normalized name becomes one channel numbered
from the group's configured start. Re-runs are stable: existing channels keep
their number and identity; new names get the lowest free number in the block.

Event rules map groups of one-off events ('00:55 NFL: Cowboys - Eagles 27/10'):
start time and date are parsed from the stream name, events are keyed by
title + date, laid out chronologically (re-packed once per day), and deleted
a configurable number of hours after they start.
"""

import fcntl
import json
import logging
import os
import re
from collections import Counter
from datetime import date, datetime, time as dt_time, timedelta, timezone as dt_timezone

logger = logging.getLogger(__name__)

_LOCK_PATH = "/tmp/automap-channelarr-run.lock"
_STATE_FILENAME = "state.json"

# Quality markers that carry a rank (higher = better). Unmarked names rank 20,
# so failover order is 4K/UHD > FHD > HD > unmarked > SD.
_QUALITY_RANKS = {
    "4k": 50,
    "uhd": 50,
    "fhd": 40,
    "hd": 30,
    "sd": 10,
}
_UNMARKED_RANK = 20

# Stripped from names but carrying no rank.
_EXTRA_STRIP = ["hevc", "h265", "h.265", "50fps"]

# ISO 3166-1 alpha-2 and alpha-3 codes. Only these count as country prefixes
# and suffixes, so 'Nick JR' and 'Disney XD' keep their endings. 'TV' (Tuvalu)
# is left out - it is a common real suffix. 'UK' is not ISO (the UK is 'GB')
# but is far more common in playlists.
_COUNTRY_CODES = frozenset((
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH "
    "BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL "
    "CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET "
    "FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU "
    "GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE "
    "KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC "
    "MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC "
    "NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT "
    "PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR "
    "SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TW TZ UA "
    "UG UK UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW "
    "ABW AFG AGO AIA ALA ALB AND ARE ARG ARM ASM ATA ATF ATG AUS AUT AZE "
    "BDI BEL BEN BES BFA BGD BGR BHR BHS BIH BLM BLR BLZ BMU BOL BRA BRB "
    "BRN BTN BVT BWA CAF CAN CCK CHE CHL CHN CIV CMR COD COG COK COL COM "
    "CPV CRI CUB CUW CXR CYM CYP CZE DEU DJI DMA DNK DOM DZA ECU EGY ERI "
    "ESH ESP EST ETH FIN FJI FLK FRA FRO FSM GAB GBR GEO GGY GHA GIB GIN "
    "GLP GMB GNB GNQ GRC GRD GRL GTM GUF GUM GUY HKG HMD HND HRV HTI HUN "
    "IDN IMN IND IOT IRL IRN IRQ ISL ISR ITA JAM JEY JOR JPN KAZ KEN KGZ "
    "KHM KIR KNA KOR KWT LAO LBN LBR LBY LCA LIE LKA LSO LTU LUX LVA MAC "
    "MAF MAR MCO MDA MDG MDV MEX MHL MKD MLI MLT MMR MNE MNG MNP MOZ MRT "
    "MSR MTQ MUS MWI MYS MYT NAM NCL NER NFK NGA NIC NIU NLD NOR NPL NRU "
    "NZL OMN PAK PAN PCN PER PHL PLW PNG POL PRI PRK PRT PRY PSE PYF QAT "
    "REU ROU RUS RWA SAU SDN SEN SGP SGS SHN SJM SLB SLE SLV SMR SOM SPM "
    "SRB SSD STP SUR SVK SVN SWE SWZ SXM SYC SYR TCA TCD TGO THA TJK TKL "
    "TKM TLS TON TTO TUN TUR TUV TWN TZA UGA UKR UMI URY USA UZB VAT VCT "
    "VEN VGB VIR VNM VUT WLF WSM YEM ZAF ZMB ZWE"
).split())

_COUNTRY_PREFIX_RE = re.compile(r"^\s*([A-Za-z]{2,3})\s*[:|]\s*")
# Trailing country code: uppercase only ('TV4 SE', 'Kanal 5 | SWE'), to avoid
# eating ordinary short words.
_COUNTRY_SUFFIX_RE = re.compile(r"[\s:|\-–—.,]+([A-Z]{2,3})\s*$")
_EDGE_TRIM = " \t-–—:|.,/"
# Bracket pairs left empty after token removal, e.g. 'TNT 1 ( )'.
_EMPTY_BRACKETS_RE = re.compile(r"\(\s*\)|\[\s*\]")


# ---------------------------------------------------------------------------
# Pure logic (no Django imports) - rules parsing and name normalization
# ---------------------------------------------------------------------------

def parse_rules(text, account_names, label="", seen_groups=None, seen_starts=None):
    """Parse a rules textarea.

    Syntax, one rule per line:
        Group = start
        Group A; Group B = start          (several groups pooled in one block)
        Account/Group = start             (only streams from that account)
        # comment lines and blank lines are ignored

    A leading 'Something/' is treated as an account qualifier only when an M3U
    account with that exact name exists; otherwise the '/' belongs to the
    group name (so '24/7 Movies' works).

    `label` prefixes error locations ("event rules line 3"). Pass the same
    seen_groups/seen_starts dicts for several calls to enforce uniqueness
    across textareas.

    Returns (rules, errors). Each rule is a dict:
        {"groups": [(account_or_None, group_name), ...],
         "start": int, "line_no": int, "pool_id": str}
    """
    rules = []
    errors = []
    if seen_groups is None:
        seen_groups = {}
    if seen_starts is None:
        seen_starts = {}

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        where = f"{label}line {line_no}"

        if "=" not in line:
            errors.append(f"{where}: no '=' found: {raw.strip()}")
            continue

        left, _, right = line.rpartition("=")
        right_text = right.strip()
        target = None
        if "->" in right_text:
            start_text, _, target_text = right_text.partition("->")
            start_text = start_text.strip()
            target = target_text.strip()
            if not target:
                errors.append(f"{where}: empty target group name after '->'")
                continue
        else:
            start_text = right_text
        try:
            start = int(start_text)
        except ValueError:
            errors.append(f"{where}: start number '{start_text}' is not an integer")
            continue
        if start < 1:
            errors.append(f"{where}: start number must be >= 1, got {start}")
            continue

        groups = []
        errors_before = len(errors)
        for part in left.split(";"):
            part = part.strip()
            if not part:
                errors.append(f"{where}: empty group name")
                continue
            account = None
            group = part
            if "/" in part:
                candidate, _, rest = part.partition("/")
                if candidate.strip() in account_names and rest.strip():
                    account = candidate.strip()
                    group = rest.strip()
            pair = (account, group)
            if pair in seen_groups:
                errors.append(
                    f"{where}: group '{part}' already used on {seen_groups[pair]}"
                )
                continue
            seen_groups[pair] = where
            groups.append(pair)

        if not groups:
            if len(errors) == errors_before:
                errors.append(f"{where}: no valid groups: {raw.strip()}")
            continue

        if start in seen_starts:
            errors.append(
                f"{where}: start number {start} already used on {seen_starts[start]}"
            )
            continue
        seen_starts[start] = where

        pool_id = "|".join(
            f"{acc or ''}/{grp}" for acc, grp in sorted(groups, key=lambda p: (p[0] or "", p[1]))
        )
        rules.append({
            "groups": groups,
            "start": start,
            "target": target,
            "line_no": line_no,
            "where": where,
            "pool_id": pool_id,
        })

    return rules, errors


def validate_targets(all_rules):
    """A rule's target group name must not be a source group in another rule
    (two rules may share a target; a rule may target its own source group)."""
    errors = []
    sources = {}
    for rule in all_rules:
        for _account, group in rule["groups"]:
            sources.setdefault(group, []).append(rule)
    for rule in all_rules:
        target = rule.get("target")
        if not target:
            continue
        for other in sources.get(target, []):
            if other is not rule:
                errors.append(
                    f"{rule['where']}: target group '{target}' is a source group "
                    f"on {other['where']}"
                )
                break
    return errors


def build_strip_tokens(extra_tokens_setting):
    """Default quality/codec tokens plus user-configured extras."""
    tokens = list(_QUALITY_RANKS.keys()) + list(_EXTRA_STRIP)
    for part in (extra_tokens_setting or "").split(";"):
        part = part.strip().lower()
        if part and part not in tokens:
            tokens.append(part)
    return tokens


def build_event_strip_tokens(event_tokens_setting, extra_tokens_setting):
    """Event title tokens: the event setting, or Strip tokens when it is
    empty. Quality/codec tokens are always included."""
    if (event_tokens_setting or "").strip():
        return build_strip_tokens(event_tokens_setting)
    return build_strip_tokens(extra_tokens_setting)


def parse_name_list(setting):
    """';'-separated name fragments, lower-cased; blanks dropped."""
    return [part.strip().lower() for part in (setting or "").split(";") if part.strip()]


def name_matches(name, fragments):
    """True when the name contains any of the fragments (case-insensitive)."""
    lowered = name.lower()
    return any(fragment in lowered for fragment in fragments)


def build_token_re(tokens):
    alts = "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alts})(?![A-Za-z0-9])", re.IGNORECASE)


def detect_quality(name):
    """Highest quality rank found in the raw name, or the unmarked rank."""
    best = None
    for token, rank in _QUALITY_RANKS.items():
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", name, re.IGNORECASE):
            if best is None or rank > best:
                best = rank
    return best if best is not None else _UNMARKED_RANK


def clean_display_name(name, token_re):
    """Strip country prefix/suffix and quality tokens, keep original casing/spacing."""
    cleaned = name
    prefix = _COUNTRY_PREFIX_RE.match(name)
    if prefix and prefix.group(1).upper() in _COUNTRY_CODES:
        cleaned = name[prefix.end():]
    cleaned = token_re.sub(" ", cleaned)
    cleaned = _EMPTY_BRACKETS_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(_EDGE_TRIM)
    match = _COUNTRY_SUFFIX_RE.search(cleaned)
    if match and match.group(1) in _COUNTRY_CODES:
        without_suffix = cleaned[: match.start()].strip(_EDGE_TRIM)
        if without_suffix:
            cleaned = without_suffix
    return cleaned if cleaned else name.strip()


def clean_event_title(name, token_re):
    """clean_display_name minus the country-prefix strip: a league tag like
    'NFL:' is indistinguishable from a country prefix and must survive."""
    cleaned = token_re.sub(" ", name)
    cleaned = _EMPTY_BRACKETS_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(_EDGE_TRIM)
    match = _COUNTRY_SUFFIX_RE.search(cleaned)
    if match and match.group(1) in _COUNTRY_CODES:
        without_suffix = cleaned[: match.start()].strip(_EDGE_TRIM)
        if without_suffix:
            cleaned = without_suffix
    return cleaned if cleaned else name.strip()


def normalize_key(cleaned_name):
    """Grouping key: lower-cased, all non-alphanumerics removed (unicode-aware)."""
    key = "".join(ch for ch in cleaned_name.lower() if ch.isalnum())
    return key if key else cleaned_name.lower().strip()


def pick_display_name(variants):
    """Most frequent cleaned variant; ties broken by shortest, then lexicographic."""
    counts = Counter(variants)
    return min(counts.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))[0]


def apply_quality_cap(streams_with_rank, cap_rank):
    """Drop streams marked above the cap unless nothing else would remain.
    Unmarked streams are never dropped."""
    if cap_rank is None:
        return streams_with_rank
    kept = [sr for sr in streams_with_rank if sr[1] <= max(cap_rank, _UNMARKED_RANK)]
    return kept if kept else streams_with_rank


_CAP_RANKS = {"unlimited": None, "fhd": 40, "hd": 30, "sd": 10}


# ---------------------------------------------------------------------------
# Event parsing - start time/date extraction from stream names
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
    r"(?:\s*([AaPp]\.?[Mm]\.?))?"               # optional AM/PM
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

_DEFAULT_TEMPLATE = "{date} {time} {title}"
_TEMPLATE_TOKEN_RE = re.compile(
    r"\{(title|time12|time|date|usdate|isodate|weekday)(?::([^{}]*))?\}"
)
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

    rendered = _TEMPLATE_TOKEN_RE.sub(_sub, template)
    return re.sub(r"\s+", " ", rendered).strip() or title


def template_unknown_tokens(template):
    valid = {m.span() for m in _TEMPLATE_TOKEN_RE.finditer(template)}
    return [
        m.group(0)
        for m in re.finditer(r"\{[^{}]*\}", template)
        if m.span() not in valid
    ]


# ---------------------------------------------------------------------------
# State file (orphan grace tracking + channel identity fallback)
# ---------------------------------------------------------------------------

def _state_path(context):
    data_dir = context.get("data_dir") if isinstance(context, dict) else None
    if not data_dir:
        data_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(data_dir, _STATE_FILENAME)


def _load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("pools"), dict):
            return data
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"automap-channelarr: could not read state file {path}: {e}")
    return {"pools": {}}


def _save_state(path, state):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning(f"automap-channelarr: could not write state file {path}: {e}")


# ---------------------------------------------------------------------------
# The run itself
# ---------------------------------------------------------------------------

def _execute(settings, log, context, dry_run, triggered_by):
    from django.db import transaction
    from apps.channels.models import (
        Channel,
        ChannelGroup,
        ChannelGroupM3UAccount,
        ChannelProfile,
        ChannelProfileMembership,
        ChannelStream,
        Logo,
        Stream,
    )
    from apps.epg.models import EPGData
    from apps.m3u.models import M3UAccount

    prefix = "automap-channelarr"
    account_names = set(M3UAccount.objects.values_list("name", flat=True))

    seen_groups = {}
    seen_starts = {}
    rules, errors = parse_rules(
        settings.get("rules", "") or "", account_names,
        label="rules ", seen_groups=seen_groups, seen_starts=seen_starts,
    )
    event_rules, event_errors = parse_rules(
        settings.get("event_rules", "") or "", account_names,
        label="event rules ", seen_groups=seen_groups, seen_starts=seen_starts,
    )
    errors += event_errors
    for rule in event_rules:
        rule["kind"] = "event"
        rule["pool_id"] = "event|" + rule["pool_id"]
    for rule in rules:
        rule["kind"] = "channel"
    errors += validate_targets(rules + event_rules)

    event_regex = None
    event_regex_text = (settings.get("event_regex") or "").strip()
    if event_regex_text:
        try:
            event_regex = re.compile(event_regex_text)
        except re.error as e:
            errors.append(f"event regex: {e}")
        else:
            if "time" not in event_regex.groupindex:
                errors.append("event regex: missing required named group (?P<time>...)")

    if errors:
        msg = "Config errors, nothing was changed: " + " | ".join(errors)
        log.error(f"{prefix}: {msg}")
        return {"status": "error", "message": msg}
    if not rules and not event_rules:
        return {"status": "success", "message": "No rules configured, nothing to do."}

    tokens = build_strip_tokens(settings.get("extra_tokens", ""))
    token_re = build_token_re(tokens)
    event_token_re = build_token_re(build_event_strip_tokens(
        settings.get("event_strip_tokens", ""), settings.get("extra_tokens", "")
    ))
    event_as_is = parse_name_list(settings.get("event_as_is", ""))
    event_not = parse_name_list(settings.get("event_not", ""))
    cap_rank =_CAP_RANKS.get(settings.get("max_quality", "unlimited"))
    try:
        grace_days = max(0, int(settings.get("orphan_grace_days", 7)))
    except (TypeError, ValueError):
        grace_days = 7

    def _hours_setting(key, default):
        try:
            value = float(settings.get(key, default))
            return value if value >= 0 else default
        except (TypeError, ValueError):
            return default

    stale_hours = _hours_setting("event_stale_hours", 6)
    lead_hours = _hours_setting("event_lead_hours", 36)
    template = (settings.get("event_name_template") or "").strip() or _DEFAULT_TEMPLATE

    state_file = _state_path(context)
    state = _load_state(state_file)
    now = datetime.now(dt_timezone.utc)
    now_local = now.astimezone()
    local_tz = now_local.tzinfo
    today_local = now_local.date()

    warnings = []
    summary = []
    created = renumbered = updated = deleted = 0

    unknown_tokens = template_unknown_tokens(template)
    if unknown_tokens:
        warnings.append(
            "event name template: unknown token(s) left as-is: " + ", ".join(unknown_tokens)
        )

    # Pass 1: resolve groups, pool streams, normalize.
    pools = []  # one entry per rule
    ambig_date_pairs = []  # (first, second) from every ambiguous event date
    for rule in rules + event_rules:
        is_event = rule["kind"] == "event"
        rule_streams = []  # (group_index, Stream, rank)
        target_group = None
        if rule["target"]:
            # Created later, inside the transaction, if it does not exist yet.
            target_group = ChannelGroup.objects.filter(name=rule["target"]).first()
        found_source = False
        for gi, (account, group_name) in enumerate(rule["groups"]):
            cg = ChannelGroup.objects.filter(name=group_name).first()
            if cg is None:
                warnings.append(f"group '{group_name}' not found, skipped")
                continue
            found_source = True
            if target_group is None and not rule["target"]:
                target_group = cg
            clash = ChannelGroupM3UAccount.objects.filter(
                channel_group=cg, enabled=True, auto_channel_sync=True
            )
            if account:
                clash = clash.filter(m3u_account__name=account)
            if clash.exists():
                warnings.append(
                    f"group '{group_name}' still has the built-in automapper "
                    f"(auto channel sync) enabled - disable it to stop the two fighting"
                )
            qs = Stream.objects.filter(channel_group=cg, is_stale=False)
            if account:
                qs = qs.filter(m3u_account__name=account)
            for stream in qs.order_by("id"):
                rule_streams.append((gi, stream, detect_quality(stream.name)))

        if not found_source:
            continue

        if is_event:
            raw_events = []
            for _gi, stream, rank in rule_streams:
                if name_matches(stream.name, event_not):
                    continue
                time_part, date_part, spans = extract_event_fields(stream.name, event_regex)
                raw_events.append((stream, rank, time_part, date_part, spans))
                if date_part is not None and date_part[0] == "ambig":
                    ambig_date_pairs.append((date_part[1], date_part[2]))
            pools.append({
                "rule": rule,
                "kind": "event",
                "target_group": target_group,
                "raw_events": raw_events,
            })
            continue

        # Group by normalized key, preserving provider order of first appearance.
        key_order = []
        by_key = {}
        for gi, stream, rank in rule_streams:
            cleaned = clean_display_name(stream.name, token_re)
            key = normalize_key(cleaned)
            if key not in by_key:
                by_key[key] = {"streams": [], "variants": [], "first_pos": (gi, stream.id)}
                key_order.append(key)
            by_key[key]["streams"].append((stream, rank))
            by_key[key]["variants"].append(cleaned)

        if not key_order:
            warnings.append(
                f"{rule['where']}: no current streams, "
                f"skipping (orphan grace timers still advance)"
            )

        # Order streams within each key, apply the quality cap.
        for key in key_order:
            entry = by_key[key]
            entry["streams"].sort(
                key=lambda sr: (-sr[1], sr[0].m3u_account_id or 0, sr[0].id)
            )
            entry["streams"] = apply_quality_cap(entry["streams"], cap_rank)
            entry["display"] = pick_display_name(entry["variants"])

        pools.append({
            "rule": rule,
            "kind": "channel",
            "target_group": target_group,
            "key_order": key_order,
            "stale_keys": [],
            "deferred_keys": [],
            "by_key": by_key,
        })

    # Event pools: resolve dates with the batch-wide day/month order, group by
    # title + date, sort chronologically, split into active/stale/deferred.
    date_order = infer_day_month_order(ambig_date_pairs, today_local)
    stale_cutoff = now_local - timedelta(hours=stale_hours)
    for pool in pools:
        if pool["kind"] != "event":
            continue
        by_key = {}
        for stream, rank, time_part, date_part, spans in pool.pop("raw_events"):
            as_is = name_matches(stream.name, event_as_is)
            if as_is:
                cleaned = stream.name.strip()
            else:
                cleaned = clean_event_title(_blank_spans(stream.name, spans), event_token_re)
            start_dt = None
            date_key = ""
            if time_part is not None:
                event_date = resolve_event_date(date_part, date_order, today_local)
                if event_date is None:
                    event_date = today_local
                start_dt = build_start_dt(time_part, event_date, local_tz)
                date_key = event_date.isoformat()
            key = normalize_key(cleaned) + "|" + date_key
            entry = by_key.get(key)
            if entry is None:
                entry = by_key[key] = {
                    "streams": [], "variants": [], "start_dt": start_dt, "channel": None,
                    "as_is": as_is,
                }
            entry["streams"].append((stream, rank))
            entry["variants"].append(cleaned)
            if start_dt is not None and (
                entry["start_dt"] is None or start_dt < entry["start_dt"]
            ):
                entry["start_dt"] = start_dt

        for entry in by_key.values():
            entry["streams"].sort(
                key=lambda sr: (-sr[1], sr[0].m3u_account_id or 0, sr[0].id)
            )
            entry["streams"] = apply_quality_cap(entry["streams"], cap_rank)
            entry["display"] = pick_display_name(entry["variants"])
            if entry["as_is"]:
                entry["render"] = entry["display"]
            else:
                entry["render"] = render_event_name(template, entry["display"], entry["start_dt"])

        if not by_key:
            warnings.append(
                f"{pool['rule']['where']}: no current streams, "
                f"skipping (orphan grace timers still advance)"
            )

        ordered = sorted(
            by_key,
            key=lambda k: (
                by_key[k]["start_dt"] is None,
                by_key[k]["start_dt"].timestamp() if by_key[k]["start_dt"] else 0.0,
                by_key[k]["render"],
            ),
        )
        active, stale_keys, deferred = [], [], []
        for key in ordered:
            start_dt = by_key[key]["start_dt"]
            if start_dt is not None and start_dt <= stale_cutoff:
                stale_keys.append(key)
            elif (
                start_dt is not None
                and lead_hours > 0
                and start_dt - now_local > timedelta(hours=lead_hours)
            ):
                deferred.append(key)
            else:
                active.append(key)
        pool["by_key"] = by_key
        pool["key_order"] = active
        pool["stale_keys"] = stale_keys
        pool["deferred_keys"] = deferred

    # Ownership matching across all pools, so a channel is claimed once.
    claimed_channel_ids = set()
    for pool in pools:
        by_key = pool["by_key"]
        pool_state = state["pools"].get(pool["rule"]["pool_id"], {})
        all_stream_ids = [
            s.id for e in by_key.values() for (s, _r) in e["streams"]
        ]
        key_by_stream = {
            s.id: key for key, e in by_key.items() for (s, _r) in e["streams"]
        }
        links = {}
        for cs in (
            ChannelStream.objects.filter(stream_id__in=all_stream_ids)
            .select_related("channel")
        ):
            key = key_by_stream.get(cs.stream_id)
            if key is not None:
                links.setdefault(key, []).append(cs.channel)

        group_channels = None  # lazy: channels in the target group, for name fallback
        for key in pool["key_order"] + pool["stale_keys"]:
            entry = by_key[key]
            channel = None
            # 1. stream-link match
            candidates = [
                c for c in links.get(key, []) if c.id not in claimed_channel_ids
            ]
            if candidates:
                channel = min(candidates, key=lambda c: (c.channel_number, c.id))
                if len({c.id for c in candidates}) > 1:
                    warnings.append(
                        f"'{entry['display']}': streams spread over "
                        f"{len({c.id for c in candidates})} channels, using "
                        f"#{channel.channel_number:g}"
                    )
            # 2. state uuid match (channel lost all its streams)
            if channel is None:
                uuid = (pool_state.get(key) or {}).get("uuid")
                if uuid:
                    channel = Channel.objects.filter(uuid=uuid).first()
                    if channel is not None and channel.id in claimed_channel_ids:
                        channel = None
            # 3. name match within the target group (exact rendered name for
            #    events, normalized name for regular channels)
            if channel is None and pool["target_group"] is not None:
                if group_channels is None:
                    group_channels = list(
                        Channel.objects.filter(channel_group=pool["target_group"])
                    )
                for c in group_channels:
                    if c.id in claimed_channel_ids:
                        continue
                    if pool["kind"] == "event":
                        if c.name == entry["render"]:
                            channel = c
                            break
                    elif normalize_key(clean_display_name(c.name, token_re)) == key:
                        channel = c
                        break
            entry["channel"] = channel
            if channel is not None:
                claimed_channel_ids.add(channel.id)

    # Deletions: keys in state that are gone from the provider.
    channels_to_delete = []  # (pool_id, key, Channel, reason)
    configured_pool_ids = {p["rule"]["pool_id"] for p in pools}
    for pool_id in list(state["pools"].keys()):
        if pool_id not in configured_pool_ids:
            # Rule removed from config: stop managing, keep the channels.
            del state["pools"][pool_id]
            continue
    for pool in pools:
        pool_id = pool["rule"]["pool_id"]
        pool_state = state["pools"].setdefault(pool_id, {})
        current_keys = (
            set(pool["key_order"]) | set(pool["stale_keys"]) | set(pool["deferred_keys"])
        )
        for key, info in list(pool_state.items()):
            if key in current_keys:
                info["missing_since"] = None
                continue
            channel = Channel.objects.filter(uuid=info.get("uuid")).first()
            if channel is None:
                del pool_state[key]
                continue
            if channel.id in claimed_channel_ids:
                # Stale entry: the channel is still mapped, under a different
                # key (e.g. after a normalization change). Never delete it.
                del pool_state[key]
                continue
            if not info.get("missing_since"):
                info["missing_since"] = now.isoformat()
                warnings.append(
                    f"'{channel.name}' (#{channel.channel_number:g}) gone from provider, "
                    f"deleting after {grace_days} day(s) if it stays gone"
                )
                continue
            try:
                missing_since = datetime.fromisoformat(info["missing_since"])
            except (ValueError, TypeError):
                info["missing_since"] = now.isoformat()
                continue
            if (now - missing_since).days >= grace_days:
                channels_to_delete.append(
                    (pool_id, key, channel,
                     f"gone from provider for >= {grace_days} day(s)")
                )

    # Stale events: started more than stale_hours ago, delete regardless of
    # whether the provider still lists them. No grace period.
    for pool in pools:
        if pool["kind"] != "event":
            continue
        pool_id = pool["rule"]["pool_id"]
        for key in pool["stale_keys"]:
            channel = pool["by_key"][key]["channel"]
            if channel is not None:
                channels_to_delete.append(
                    (pool_id, key, channel,
                     f"event started more than {stale_hours:g} hour(s) ago")
                )
            else:
                state["pools"].get(pool_id, {}).pop(key, None)

    # Numbering: every existing number is occupied; deletions free theirs.
    used_numbers = set(Channel.objects.values_list("channel_number", flat=True))
    deleted_channel_ids = set()
    for _pid, _key, channel, _reason in channels_to_delete:
        used_numbers.discard(channel.channel_number)
        deleted_channel_ids.add(channel.id)
    our_numbers = {
        e["channel"].channel_number
        for p in pools
        for e in p["by_key"].values()
        if e["channel"] is not None
    }

    # Event blocks are re-packed in chronological order on the first run of
    # each server-local day; later runs only fill free slots.
    repack = bool(event_rules) and state.get("event_repack_date") != today_local.isoformat()
    plan_creates = []  # (pool, key, number, foreign_skips)
    if repack:
        for pool in pools:
            if pool["kind"] != "event":
                continue
            for key in pool["key_order"]:
                channel = pool["by_key"][key]["channel"]
                if channel is not None and channel.id not in deleted_channel_ids:
                    used_numbers.discard(channel.channel_number)
            number = float(pool["rule"]["start"])
            for key in pool["key_order"]:
                entry = pool["by_key"][key]
                skipped = 0
                while number in used_numbers:
                    skipped += 1
                    number += 1
                if skipped:
                    warnings.append(
                        f"'{entry['render']}': skipped {skipped} foreign-occupied "
                        f"number(s), landed on {number:g}"
                    )
                used_numbers.add(number)
                our_numbers.add(number)
                if entry["channel"] is None:
                    plan_creates.append((pool, key, number, skipped))
                else:
                    entry["target_number"] = number
                number += 1

    for pool in pools:
        if repack and pool["kind"] == "event":
            continue
        number = float(pool["rule"]["start"])
        for key in pool["key_order"]:
            entry = pool["by_key"][key]
            if entry["channel"] is not None:
                continue
            skipped = 0
            while number in used_numbers:
                if number not in our_numbers:
                    skipped += 1
                number += 1
            used_numbers.add(number)
            plan_creates.append((pool, key, number, skipped))
            if skipped:
                warnings.append(
                    f"'{entry['display']}': skipped {skipped} foreign-occupied "
                    f"number(s), landed on {number:g}"
                )
            number += 1

    # Apply (or narrate, when dry-running).
    def _sync_epg(channel, primary_stream):
        changed_fields = []
        tvg_id = primary_stream.tvg_id
        if tvg_id:
            if channel.tvg_id != tvg_id:
                channel.tvg_id = tvg_id
                changed_fields.append("tvg_id")
            epg = EPGData.objects.filter(tvg_id=tvg_id).first()
            if epg is not None and channel.epg_data_id != epg.id:
                channel.epg_data = epg
                changed_fields.append("epg_data")
        return changed_fields

    def _sync_streams(channel, ordered_streams, apply):
        changes = 0
        target_ids = [s.id for s, _r in ordered_streams]
        existing = {cs.stream_id: cs for cs in ChannelStream.objects.filter(channel=channel)}
        for sid, cs in existing.items():
            if sid not in target_ids:
                changes += 1
                if apply:
                    cs.delete()
        for order, sid in enumerate(target_ids):
            cs = existing.get(sid)
            if cs is None:
                changes += 1
                if apply:
                    ChannelStream.objects.create(channel=channel, stream_id=sid, order=order)
            elif cs.order != order:
                changes += 1
                if apply:
                    cs.order = order
                    cs.save(update_fields=["order"])
        return changes

    verb = "would " if dry_run else ""
    with transaction.atomic():
        for pool in pools:
            pool_id = pool["rule"]["pool_id"]
            pool_state = state["pools"].setdefault(pool_id, {})
            pool_created = pool_updated = 0
            is_event = pool["kind"] == "event"

            if pool["target_group"] is None:
                # Explicit '-> Name' target that does not exist yet. Created
                # here so a dry run rolls it back with everything else.
                pool["target_group"], group_created = ChannelGroup.objects.get_or_create(
                    name=pool["rule"]["target"]
                )
                if group_created:
                    log.info(
                        f"{prefix}: {verb}create channel group "
                        f"'{pool['rule']['target']}'"
                    )

            for key in pool["key_order"]:
                entry = pool["by_key"][key]
                channel = entry["channel"]
                if channel is None:
                    continue
                pool_state[key] = {"uuid": str(channel.uuid), "missing_since": None}
                changed = _sync_epg(channel, entry["streams"][0][0])
                if is_event:
                    if channel.name != entry["render"]:
                        channel.name = entry["render"]
                        changed.append("name")
                    target_number = entry.get("target_number")
                    if target_number is not None and channel.channel_number != target_number:
                        channel.channel_number = target_number
                        changed.append("channel_number")
                        renumbered += 1
                if changed and not dry_run:
                    channel.save(update_fields=changed)
                stream_changes = _sync_streams(channel, entry["streams"], apply=not dry_run)
                if changed or stream_changes:
                    pool_updated += 1
                    log.info(
                        f"{prefix}: {verb}update '{channel.name}' "
                        f"(#{channel.channel_number:g}): "
                        f"{'+'.join(changed) or 'streams'} "
                        f"({len(entry['streams'])} stream(s))"
                    )

            for cpool, key, number, _skipped in plan_creates:
                if cpool is not pool:
                    continue
                entry = pool["by_key"][key]
                primary = entry["streams"][0][0]
                display = entry["render"] if is_event else entry["display"]
                log.info(
                    f"{prefix}: {verb}create '{display}' at #{number:g} "
                    f"with {len(entry['streams'])} stream(s) "
                    f"in group '{pool['target_group'].name}'"
                )
                pool_created += 1
                if dry_run:
                    continue
                channel = Channel.objects.create(
                    channel_number=number,
                    name=display,
                    tvg_id=primary.tvg_id,
                    channel_group=pool["target_group"],
                    user_level=0,
                )
                if primary.logo_url:
                    logo, _ = Logo.objects.get_or_create(
                        url=primary.logo_url,
                        defaults={"name": display or primary.tvg_id or "Unknown"},
                    )
                    channel.logo = logo
                changed = _sync_epg(channel, primary)
                channel.save()
                _sync_streams(channel, entry["streams"], apply=True)
                memberships = [
                    ChannelProfileMembership(
                        channel_profile=profile, channel=channel, enabled=True
                    )
                    for profile in ChannelProfile.objects.all()
                ]
                if memberships:
                    ChannelProfileMembership.objects.bulk_create(memberships)
                pool_state[key] = {"uuid": str(channel.uuid), "missing_since": None}

            created += pool_created
            updated += pool_updated
            group_names = ", ".join(g for _a, g in pool["rule"]["groups"])
            summary.append(
                f"{group_names}: {pool_created} created, {pool_updated} updated"
            )

        for pool_id, key, channel, reason in channels_to_delete:
            log.info(
                f"{prefix}: {verb}delete '{channel.name}' "
                f"(#{channel.channel_number:g}), {reason}"
            )
            deleted += 1
            if not dry_run:
                channel.delete()
                state["pools"].get(pool_id, {}).pop(key, None)

        if dry_run:
            transaction.set_rollback(True)

    if event_rules and repack:
        state["event_repack_date"] = today_local.isoformat()

    if not dry_run:
        _save_state(state_file, state)

    for w in warnings:
        log.warning(f"{prefix}: {w}")

    headline = (
        f"{'DRY RUN - ' if dry_run else ''}{created} created, {updated} updated, "
        f"{renumbered} renumbered, {deleted} deleted"
        + (f", {len(warnings)} warning(s) (see logs)" if warnings else "")
    )
    log.info(f"{prefix}: run complete ({triggered_by}): {headline} | " + " | ".join(summary))

    if not dry_run:
        try:
            from core.utils import send_websocket_update
            send_websocket_update(
                "updates",
                "update",
                {"type": "plugin", "plugin": "automap_channelarr", "message": headline},
            )
        except Exception as e:
            log.warning(f"{prefix}: could not send websocket update: {e}")

    return {"status": "success", "message": headline}


def _locked_execute(settings, log, context, dry_run, triggered_by):
    try:
        fh = open(_LOCK_PATH, "w")
    except OSError as e:
        return {"status": "error", "message": f"Could not open lock file: {e}"}
    try:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return {
                "status": "success",
                "message": "Another Automap Channelarr run is already in progress, skipping.",
            }
        return _execute(settings, log, context, dry_run, triggered_by)
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        except Exception:
            pass
        fh.close()


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class Plugin:
    name = "Automap Channelarr"
    version = "0.2.0"
    description = (
        "Deterministic rule-based channel mapper: pools each M3U group's streams "
        "by normalized name and lays them out as channels from a configured "
        "start number. Event groups become schedule-ordered, self-cleaning "
        "channel blocks. Replaces the built-in automapper."
    )
    author = "Megamannen"

    fields = [
        {
            "id": "auto_run",
            "label": "Run automatically after each M3U refresh",
            "type": "boolean",
            "default": False,
        },
        {
            "id": "rules_info",
            "label": "Rules",
            "type": "info",
            "description": (
                "One rule per line: 'Group = start'. Pool several groups into one "
                "block with ';' ('Sports; Sport HD = 100'). Restrict a group to one "
                "M3U account with 'Account/Group = 100'. Append '-> Name' to place "
                "the channels in that channel group ('Sports = 100 -> My Sports'), "
                "created if missing. Lines starting with # are comments. Disable "
                "the built-in auto channel sync on these groups."
            ),
        },
        {
            "id": "rules",
            "label": "Rules",
            "type": "text",
            "default": "",
            "placeholder": "# Sports; Sport HD = 100\n# News = 200\n# ProviderX/Kids = 300",
        },
        {
            "id": "extra_tokens",
            "label": "Strip tokens",
            "type": "string",
            "default": "",
            "placeholder": "RAW; VIP; Multi",
            "help_text": (
                "Extra tokens removed from names before grouping, separated by ';'. "
                "Also used for event titles when Event strip tokens is empty. "
                "4K, UHD, FHD, HD, SD, HEVC, H265 and 50FPS are always removed."
            ),
        },
        {
            "id": "max_quality",
            "label": "Preferred max quality",
            "type": "select",
            "default": "unlimited",
            "options": [
                {"value": "unlimited", "label": "Unlimited"},
                {"value": "fhd", "label": "FHD"},
                {"value": "hd", "label": "HD"},
                {"value": "sd", "label": "SD"},
            ],
            "help_text": (
                "Streams marked above this quality are left out of channels - "
                "unless they are all a channel has. Saves bandwidth by skipping "
                "e.g. 4K when an FHD stream exists. Applies to event channels too."
            ),
        },
        {
            "id": "orphan_grace_days",
            "label": "Orphan grace period (days)",
            "type": "number",
            "default": 7,
            "help_text": (
                "A mapped channel whose streams disappear from the provider is "
                "deleted only after being gone this many days in a row. "
                "0 deletes immediately. Applies to event channels too."
            ),
        },
        {
            "id": "event_rules_info",
            "label": "Event rules",
            "type": "info",
            "description": (
                "Same syntax as Rules, for groups of one-off events ('00:55 NFL: "
                "Cowboys - Eagles 27/10'). Start time and date are parsed from each "
                "stream name; events become channels sorted by start time and are "
                "removed after they have started. A group may appear in Rules or "
                "Event rules, not both."
            ),
        },
        {
            "id": "event_rules",
            "label": "Event rules",
            "type": "text",
            "default": "",
            "placeholder": "# PPV Events = 5000\n# NXT IPTV/Live Sports = 6000 -> Events",
        },
        {
            "id": "event_strip_tokens",
            "label": "Event strip tokens",
            "type": "string",
            "default": "",
            "placeholder": "NXTSE; Viaplay SE; Disney SE",
            "help_text": (
                "Tokens removed from event titles, separated by ';'. Empty uses "
                "Strip tokens. 4K, UHD, FHD, HD, SD, HEVC, H265 and 50FPS "
                "are always removed."
            ),
        },
        {
            "id": "event_as_is",
            "label": "Event as is",
            "type": "string",
            "default": "",
            "placeholder": "RedZone; Big Fight Night",
            "help_text": (
                "Event streams whose name contains any of these ';'-separated "
                "texts (case-insensitive) keep their stream name as channel name: "
                "no stripping, no name template. The start time is still read "
                "for ordering and removal."
            ),
        },
        {
            "id": "event_not",
            "label": "Event not",
            "type": "string",
            "default": "",
            "placeholder": "Replay; Highlights",
            "help_text": (
                "Event streams whose name contains any of these ';'-separated "
                "texts (case-insensitive) are skipped. Wins over Event as is."
            ),
        },
        {
            "id": "event_regex",
            "label": "Event regex",
            "type": "string",
            "default": "",
            "placeholder": r"^(?P<time>\d{1,2}:\d{2}).*?(?P<date>\d{1,2}/\d{1,2})",
            "help_text": (
                "Optional. Overrides the built-in time/date detection for event "
                "streams. Must contain a named group (?P<time>...); (?P<date>...) "
                "is optional (no date = today). Streams it does not match fall "
                "back to the built-in parser."
            ),
        },
        {
            "id": "event_name_template",
            "label": "Event name template",
            "type": "string",
            "default": _DEFAULT_TEMPLATE,
            "placeholder": _DEFAULT_TEMPLATE,
            "help_text": (
                "Tokens: {title}, {time} 22:00, {time12} 10:00 PM, {date} 27/10, "
                "{usdate} 10/27, {isodate} 2026-10-27, {weekday} Mon. Custom "
                "weekday names: {weekday:Man,Tis,Ons,Tor,Fre,Lor,Son} (7 names, "
                "Monday first). Times are server-local."
            ),
        },
        {
            "id": "event_lead_hours",
            "label": "Event lead time (hours before start)",
            "type": "number",
            "default": 36,
            "help_text": (
                "Events starting further ahead than this are not created yet. "
                "0 creates everything the provider publishes."
            ),
        },
        {
            "id": "event_stale_hours",
            "label": "Event removal (hours after start)",
            "type": "number",
            "default": 6,
            "help_text": (
                "An event channel is deleted this many hours after its start "
                "time, even if the provider still lists it. Checked on every run."
            ),
        },
    ]

    actions = [
        {
            "id": "run_now",
            "label": "Run Now",
            "description": "Apply the mapping rules immediately.",
            "button_label": "Run Now",
            "button_variant": "filled",
            "button_color": "blue",
            "confirm": {
                "required": True,
                "title": "Run Automap Channelarr?",
                "message": (
                    "This will create, renumber and delete channels according to "
                    "the configured rules. Run a Dry Run first if unsure."
                ),
            },
        },
        {
            "id": "dry_run",
            "label": "Dry Run",
            "description": "Compute and log every planned change without touching anything.",
            "button_label": "Dry Run",
            "button_variant": "outline",
            "button_color": "gray",
        },
        {
            "id": "m3u_refresh_hook",
            "label": "Auto Run Hook",
            "description": (
                "Fires automatically after each M3U refresh when 'Run automatically' "
                "is enabled. Clicking it manually behaves like Run Now."
            ),
            "button_label": "Trigger Hook",
            "button_variant": "subtle",
            "button_color": "gray",
            "events": ["m3u_refresh"],
        },
    ]

    def run(self, action: str, params: dict, context: dict):
        log = context.get("logger", logger)
        settings = context.get("settings", {}) or {}

        try:
            if action == "run_now":
                return _locked_execute(settings, log, context, dry_run=False, triggered_by="manual")

            if action == "dry_run":
                return _locked_execute(settings, log, context, dry_run=True, triggered_by="dry-run")

            if action == "m3u_refresh_hook":
                is_event = bool((params or {}).get("event"))
                if is_event and not settings.get("auto_run", False):
                    log.debug("automap-channelarr: m3u_refresh received but auto run is disabled")
                    return {"status": "success", "message": "Auto run disabled, skipped."}
                triggered_by = "m3u_refresh" if is_event else "manual hook"
                return _locked_execute(settings, log, context, dry_run=False, triggered_by=triggered_by)
        except Exception as e:
            log.exception(f"automap-channelarr: action '{action}' failed")
            return {"status": "error", "message": f"Run failed: {e}"}

        return {"status": "error", "message": f"Unknown action: {action}"}
