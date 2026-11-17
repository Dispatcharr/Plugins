"""Configuration: the rules textareas and every other setting, parsed once
into an immutable Config. No Django imports."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Quality markers that carry a rank (higher = better). Unmarked names rank 20,
# so failover order is 4K/UHD > FHD > HD > unmarked > SD. Resolution markers
# rank with their tier.
QUALITY_RANKS = {
    "4k": 50,
    "uhd": 50,
    "2160p": 50,
    "fhd": 40,
    "1080p": 40,
    "1080i": 40,
    "hd": 30,
    "720p": 30,
    "sd": 10,
    "576p": 10,
    "576i": 10,
    "480p": 10,
    "480i": 10,
}
UNMARKED_RANK = 20

# Stripped from names but carrying no rank.
EXTRA_STRIP = ["hevc", "h265", "h.265", "50fps"]

CAP_RANKS = {"unlimited": None, "fhd": 40, "hd": 30, "sd": 10}

DEFAULT_TEMPLATE = "{date} {time} {title}"
TEMPLATE_TOKEN_RE = re.compile(
    r"\{(title|time12|time|date|usdate|isodate|weekday)(?::([^{}]*))?\}"
)


@dataclass(frozen=True)
class Rule:
    groups: tuple  # ((account_or_None, group_name), ...)
    start: int
    target: str | None
    where: str  # "rules line 3", for error messages
    pool_id: str
    kind: str  # "channel" or "event"


@dataclass(frozen=True)
class Config:
    rules: tuple  # channel Rules
    event_rules: tuple  # event Rules
    token_re: re.Pattern
    event_token_re: re.Pattern
    event_as_is: tuple
    event_not: tuple
    event_regex: re.Pattern | None
    cap_rank: int | None
    grace_days: int
    lead_hours: float
    stale_hours: float
    template: str


def load_config(settings, account_names):
    """Parse the plugin settings dict.

    Returns (config, errors, warnings). `config` is None when `errors` is
    non-empty. `account_names` is the set of existing M3U account names,
    used to tell 'Account/Group' from a group name containing '/'.
    """
    settings = settings or {}
    errors = []
    warnings = []

    seen_groups = {}
    seen_starts = {}
    rules, rule_errors = _parse_rules(
        settings.get("rules") or "", account_names, "channel", "rules ",
        seen_groups, seen_starts,
    )
    event_rules, event_errors = _parse_rules(
        settings.get("event_rules") or "", account_names, "event", "event rules ",
        seen_groups, seen_starts,
    )
    errors += rule_errors + event_errors
    errors += _validate_targets(rules + event_rules)

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
        return None, errors, warnings

    template = (settings.get("event_name_template") or "").strip() or DEFAULT_TEMPLATE
    unknown_tokens = template_unknown_tokens(template)
    if unknown_tokens:
        warnings.append(
            "event name template: unknown token(s) left as-is: " + ", ".join(unknown_tokens)
        )

    extra_tokens = settings.get("extra_tokens", "")
    event_tokens = settings.get("event_strip_tokens", "")
    config = Config(
        rules=rules,
        event_rules=event_rules,
        token_re=build_token_re(build_strip_tokens(extra_tokens)),
        event_token_re=build_token_re(
            build_strip_tokens(event_tokens if (event_tokens or "").strip() else extra_tokens)
        ),
        event_as_is=_name_list(settings.get("event_as_is", "")),
        event_not=_name_list(settings.get("event_not", "")),
        event_regex=event_regex,
        cap_rank=CAP_RANKS.get(settings.get("max_quality", "unlimited")),
        grace_days=_int_setting(settings, "orphan_grace_days", 7),
        lead_hours=_hours_setting(settings, "event_lead_hours", 36),
        stale_hours=_hours_setting(settings, "event_stale_hours", 6),
        template=template,
    )
    return config, errors, warnings


def build_strip_tokens(extra_tokens_setting):
    """Default quality/codec tokens plus ';'-separated extras."""
    tokens = list(QUALITY_RANKS.keys()) + list(EXTRA_STRIP)
    for part in (extra_tokens_setting or "").split(";"):
        part = part.strip().lower()
        if part and part not in tokens:
            tokens.append(part)
    return tokens


def build_token_re(tokens):
    alts = "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alts})(?![A-Za-z0-9])", re.IGNORECASE)


def template_unknown_tokens(template):
    valid = {m.span() for m in TEMPLATE_TOKEN_RE.finditer(template)}
    return [
        m.group(0)
        for m in re.finditer(r"\{[^{}]*\}", template)
        if m.span() not in valid
    ]


def _parse_rules(text, account_names, kind, label, seen_groups, seen_starts):
    """One rule per line:
        Group = start
        Group A; Group B = start          (several groups pooled in one block)
        Account/Group = start             (only streams from that account)
        Group = start -> Target           (channels placed in that group)
        # comment lines and blank lines are ignored

    A leading 'Something/' is an account qualifier only when an M3U account
    with that exact name exists; otherwise the '/' belongs to the group name
    (so '24/7 Movies' works). seen_groups/seen_starts are shared between the
    two textareas so a group or start number is used once overall.
    """
    rules = []
    errors = []
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
            f"{acc or ''}/{grp}"
            for acc, grp in sorted(groups, key=lambda p: (p[0] or "", p[1]))
        )
        if kind == "event":
            pool_id = "event|" + pool_id
        rules.append(Rule(
            groups=tuple(groups),
            start=start,
            target=target,
            where=where,
            pool_id=pool_id,
            kind=kind,
        ))
    return tuple(rules), errors


def _validate_targets(all_rules):
    """A rule's target group must not be a source group in another rule (two
    rules may share a target; a rule may target its own source group)."""
    errors = []
    sources = {}
    for rule in all_rules:
        for _account, group in rule.groups:
            sources.setdefault(group, []).append(rule)
    for rule in all_rules:
        if not rule.target:
            continue
        for other in sources.get(rule.target, []):
            if other is not rule:
                errors.append(
                    f"{rule.where}: target group '{rule.target}' is a source group "
                    f"on {other.where}"
                )
                break
    return errors


def _name_list(setting):
    """';'-separated name fragments, lower-cased; blanks dropped."""
    return tuple(
        part.strip().lower() for part in (setting or "").split(";") if part.strip()
    )


def _int_setting(settings, key, default):
    try:
        return max(0, int(settings.get(key, default)))
    except (TypeError, ValueError):
        return default


def _hours_setting(settings, key, default):
    try:
        value = float(settings.get(key, default))
        return value if value >= 0 else default
    except (TypeError, ValueError):
        return default
