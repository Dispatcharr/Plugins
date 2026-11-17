"""Channel names: normalization, grouping into Entries, and the StreamInfo
and Entry types shared with events.py. No Django imports."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from .config import QUALITY_RANKS, UNMARKED_RANK


@dataclass(frozen=True)
class StreamInfo:
    """The five facts about a stream the mapping logic depends on."""
    id: int
    name: str
    tvg_id: str | None = None
    m3u_account_id: int | None = None
    logo_url: str | None = None


@dataclass(frozen=True)
class Entry:
    """One would-be channel. Channel and event pools produce the same shape."""
    key: str  # grouping key, unique within its pool
    name: str  # channel name to apply
    name_keys: tuple  # names an existing channel may be claimed by
    streams: tuple  # StreamInfo in failover order, after the quality cap
    start_dt: datetime | None = None  # events only


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
# Bracket pairs left empty, or holding only separators, after token removal,
# e.g. 'TNT 1 ( )', 'TNT 1 ( / )'.
_EMPTY_BRACKETS_RE = re.compile(r"\([^\w()]*\)|\[[^\w\[\]]*\]")
# Numbered or lettered provider tags on regular channels: 'TV4 (1)', 'TV4 (B)'.
_PAREN_TAG_RE = re.compile(r"\(\s*(?:\d+|[A-Za-z])\s*\)")
# tvg-id placeholders that mean "no tvg-id".
_TVG_ID_PLACEHOLDERS = frozenset(("null", "undefined"))
_QUALITY_RES = [
    (re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", re.IGNORECASE), rank)
    for token, rank in QUALITY_RANKS.items()
]


def build_channel_entries(streams, config):
    """Group a pool's streams into Entries by normalized name, merging names
    that share a tvg-id, in provider order of first appearance."""
    named = [(stream, clean_display_name(stream.name, config.token_re)) for stream in streams]
    group_of = merge_keys_by_tvg_id(
        (normalize_key(cleaned), stream.tvg_id) for stream, cleaned in named
    )
    order = []
    members = {}
    variants = {}
    name_keys = {}
    for stream, cleaned in named:
        name_key = normalize_key(cleaned)
        key = group_of[name_key]
        if key not in members:
            order.append(key)
            members[key], variants[key], name_keys[key] = [], [], []
        members[key].append(stream)
        variants[key].append(cleaned)
        if name_key not in name_keys[key]:
            name_keys[key].append(name_key)
    return tuple(
        Entry(
            key=key,
            name=pick_display_name(variants[key]),
            name_keys=tuple(name_keys[key]),
            streams=order_streams(members[key], config.cap_rank),
        )
        for key in order
    )


def order_streams(streams, cap_rank):
    """Failover order: quality rank, then account, then stream id; then the
    quality cap."""
    ranked = sorted(
        ((stream, detect_quality(stream.name)) for stream in streams),
        key=lambda sr: (-sr[1], sr[0].m3u_account_id or 0, sr[0].id),
    )
    return tuple(stream for stream, _rank in apply_quality_cap(ranked, cap_rank))


def name_matches(name, fragments):
    """True when the name contains any of the fragments (case-insensitive)."""
    lowered = name.lower()
    return any(fragment in lowered for fragment in fragments)


def detect_quality(name):
    """Highest quality rank found in the raw name, or the unmarked rank."""
    best = None
    for pattern, rank in _QUALITY_RES:
        if pattern.search(name):
            if best is None or rank > best:
                best = rank
    return best if best is not None else UNMARKED_RANK


def clean_display_name(name, token_re):
    """Strip country prefix/suffix, quality tokens and '(N)'/'(X)' tags, keep
    original casing/spacing."""
    cleaned = name
    prefix = _COUNTRY_PREFIX_RE.match(name)
    if prefix and prefix.group(1).upper() in _COUNTRY_CODES:
        cleaned = name[prefix.end():]
    cleaned = token_re.sub(" ", cleaned)
    cleaned = _PAREN_TAG_RE.sub(" ", cleaned)
    return _finish_cleaning(name, cleaned)


def clean_event_title(name, token_re):
    """clean_display_name minus the country-prefix strip: a league tag like
    'NFL:' is indistinguishable from a country prefix and must survive."""
    return _finish_cleaning(name, token_re.sub(" ", name))


def _finish_cleaning(name, cleaned):
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


def valid_tvg_id(tvg_id):
    """Lower-cased tvg-id, or None when blank or a 'null'/'undefined' placeholder."""
    value = (tvg_id or "").strip().lower()
    return value if value and value not in _TVG_ID_PLACEHOLDERS else None


def merge_keys_by_tvg_id(pairs):
    """Map each name key to its group key. Name keys sharing a valid tvg-id are
    merged, transitively. `pairs` is (name_key, tvg_id) in provider order; a
    group is keyed by its first-appearing name key, so unmerged names keep
    their own key."""
    position = {}
    group_of = {}
    group_by_tvg = {}
    for name_key, tvg_id in pairs:
        position.setdefault(name_key, len(position))
        group = group_of.setdefault(name_key, name_key)
        tvg = valid_tvg_id(tvg_id)
        if tvg is None:
            continue
        other = group_by_tvg.setdefault(tvg, group)
        if other == group:
            continue
        keep, drop = sorted((group, other), key=position.get)
        group_of = {k: keep if g == drop else g for k, g in group_of.items()}
        group_by_tvg = {t: keep if g == drop else g for t, g in group_by_tvg.items()}
    return group_of


def pick_display_name(variants):
    """Most frequent cleaned variant; ties broken by shortest, then lexicographic."""
    counts = Counter(variants)
    return min(counts.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))[0]


def apply_quality_cap(streams_with_rank, cap_rank):
    """Drop streams marked above the cap unless nothing else would remain.
    Unmarked streams are never dropped."""
    if cap_rank is None:
        return streams_with_rank
    kept = [sr for sr in streams_with_rank if sr[1] <= max(cap_rank, UNMARKED_RANK)]
    return kept if kept else streams_with_rank
