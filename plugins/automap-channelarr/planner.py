"""The planner: a pure function from Config, Snapshot, MappingState and the
current time to a Plan of channel actions. No Django imports.

The Snapshot is everything the run reads from Dispatcharr, taken once. The
Plan is everything the run would change, plus the Mapping state after the run
(new channels' uuids are added by apply, since the database assigns them).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timezone as dt_timezone

from .events import build_event_entries
from .names import build_channel_entries, clean_display_name, normalize_key


@dataclass(frozen=True)
class ChannelInfo:
    id: int
    uuid: str
    name: str
    number: float
    group_id: int | None = None
    tvg_id: str | None = None
    epg_data_id: int | None = None


@dataclass(frozen=True)
class Snapshot:
    streams: dict = field(default_factory=dict)  # (account|None, group) -> (StreamInfo, ...)
    group_ids: dict = field(default_factory=dict)  # channel group name -> id
    auto_sync_clashes: frozenset = frozenset()  # (account|None, group) with built-in automapper on
    channels: dict = field(default_factory=dict)  # channel id -> ChannelInfo, every channel
    links: dict = field(default_factory=dict)  # channel id -> (stream id, ...) in order
    epg_ids: dict = field(default_factory=dict)  # tvg_id -> EPGData id


@dataclass(frozen=True)
class CreateGroup:
    name: str


@dataclass(frozen=True)
class CreateChannel:
    pool_id: str
    key: str
    number: float
    name: str
    group_name: str
    tvg_id: str | None
    epg_id: int | None
    logo_url: str | None
    stream_ids: tuple


@dataclass(frozen=True)
class UpdateChannel:
    channel_id: int
    name: str  # after the update
    number: float  # after the update
    fields: dict  # changed model fields: name, channel_number, tvg_id, epg_data (id)
    stream_ids: tuple  # wanted links, in order
    stream_changes: int  # link ops apply will make


@dataclass(frozen=True)
class DeleteChannel:
    channel_id: int
    name: str
    number: float
    reason: str


@dataclass(frozen=True)
class Plan:
    actions: tuple
    state: object  # MappingState after the run, minus created channels' uuids
    warnings: tuple
    summary: tuple  # one line per pool

    @property
    def created(self):
        return sum(1 for a in self.actions if isinstance(a, CreateChannel))

    @property
    def updated(self):
        return sum(1 for a in self.actions if isinstance(a, UpdateChannel))

    @property
    def renumbered(self):
        return sum(
            1 for a in self.actions
            if isinstance(a, UpdateChannel) and "channel_number" in a.fields
        )

    @property
    def deleted(self):
        return sum(1 for a in self.actions if isinstance(a, DeleteChannel))


def describe(action):
    """One log line per action, without the 'would ' prefix."""
    if isinstance(action, CreateGroup):
        return f"create channel group '{action.name}'"
    if isinstance(action, UpdateChannel):
        return (
            f"update '{action.name}' (#{action.number:g}): "
            f"{'+'.join(action.fields) or 'streams'} "
            f"({len(action.stream_ids)} stream(s))"
        )
    if isinstance(action, CreateChannel):
        return (
            f"create '{action.name}' at #{action.number:g} "
            f"with {len(action.stream_ids)} stream(s) in group '{action.group_name}'"
        )
    return f"delete '{action.name}' (#{action.number:g}), {action.reason}"


def headline(plan, dry_run):
    return (
        f"{'DRY RUN - ' if dry_run else ''}{plan.created} created, "
        f"{plan.updated} updated, {plan.renumbered} renumbered, {plan.deleted} deleted"
        + (f", {len(plan.warnings)} warning(s) (see logs)" if plan.warnings else "")
    )


class _Pool:
    def __init__(self, rule, target_name):
        self.rule = rule
        self.target_name = target_name
        self.entries = {}  # key -> Entry: active, stale and deferred
        self.active = []  # keys in numbering order
        self.stale = []
        self.deferred = []
        self.channels = {}  # key -> claimed ChannelInfo or None
        self.numbers = {}  # key -> number assigned by a repack

    @property
    def pool_id(self):
        return self.rule.pool_id

    @property
    def is_event(self):
        return self.rule.kind == "event"


def plan(config, snapshot, state, now_local):
    """Decide every change one run would make. `now_local` is an aware
    datetime in server-local time."""
    now = now_local.astimezone(dt_timezone.utc)
    today = now_local.date()
    warnings = []
    pools = _pool_streams(config, snapshot, warnings)
    _build_entries(pools, config, now_local, warnings)
    _claim_channels(pools, config, snapshot, state, warnings)
    state, deletions = _plan_deletions(pools, config, snapshot, state, now, warnings)
    repack = bool(config.event_rules) and state.repack_due(today)
    creates = _assign_numbers(pools, snapshot, deletions, repack, warnings)
    actions, state, summary = _plan_actions(pools, snapshot, state, creates, deletions)
    if repack:
        state = state.mark_repacked(today)
    return Plan(
        actions=tuple(actions), state=state, warnings=tuple(warnings), summary=tuple(summary)
    )


def _pool_streams(config, snapshot, warnings):
    pools = []
    for rule in config.rules + config.event_rules:
        streams = []
        target_name = rule.target
        for account, group_name in rule.groups:
            if group_name not in snapshot.group_ids:
                warnings.append(f"group '{group_name}' not found, skipped")
                continue
            if target_name is None:
                target_name = group_name
            if (account, group_name) in snapshot.auto_sync_clashes:
                warnings.append(
                    f"group '{group_name}' still has the built-in automapper "
                    f"(auto channel sync) enabled - disable it to stop the two fighting"
                )
            streams.extend(snapshot.streams.get((account, group_name), ()))
        if target_name is None:  # no source group found
            continue
        pool = _Pool(rule, target_name)
        pool.streams = streams
        pools.append(pool)
    return pools


def _build_entries(pools, config, now_local, warnings):
    for pool in pools:
        if pool.is_event:
            continue
        entries = build_channel_entries(pool.streams, config)
        pool.entries = {e.key: e for e in entries}
        pool.active = [e.key for e in entries]
        if not entries:
            warnings.append(
                f"{pool.rule.where}: no current streams, "
                f"skipping (orphan grace timers still advance)"
            )
    event_pools = [p for p in pools if p.is_event]
    results = build_event_entries([p.streams for p in event_pools], config, now_local)
    for pool, result in zip(event_pools, results):
        pool.entries = {e.key: e for e in result.active + result.stale + result.deferred}
        pool.active = [e.key for e in result.active]
        pool.stale = [e.key for e in result.stale]
        pool.deferred = [e.key for e in result.deferred]
        if not pool.entries:
            warnings.append(
                f"{pool.rule.where}: no current streams, "
                f"skipping (nothing deleted this run)"
            )
    for pool in pools:
        del pool.streams


def _claim_channels(pools, config, snapshot, state, warnings):
    """Match entries to existing channels so each channel is claimed once:
    by a shared stream link, then by remembered uuid, then by name within
    the target group."""
    channels_by_stream = {}
    for channel_id, stream_ids in snapshot.links.items():
        for stream_id in stream_ids:
            channels_by_stream.setdefault(stream_id, []).append(channel_id)
    channel_by_uuid = {c.uuid: c for c in snapshot.channels.values()}
    claimed = set()
    for pool in pools:
        target_id = snapshot.group_ids.get(pool.target_name)
        by_name = None  # lazy: target group channels by (normalized) name
        for key in pool.active + pool.stale:
            entry = pool.entries[key]
            channel = None
            linked = []
            for stream in entry.streams:
                for channel_id in channels_by_stream.get(stream.id, ()):
                    if channel_id not in claimed:
                        linked.append(snapshot.channels[channel_id])
            if linked:
                channel = min(linked, key=lambda c: (c.number, c.id))
                spread = len({c.id for c in linked})
                if spread > 1:
                    warnings.append(
                        f"'{entry.name}': streams spread over {spread} channels, "
                        f"using #{channel.number:g}"
                    )
            if channel is None:
                channel = channel_by_uuid.get(state.uuid_for(pool.pool_id, key))
                if channel is not None and channel.id in claimed:
                    channel = None
            if channel is None and target_id is not None:
                if by_name is None:
                    by_name = {}
                    for c in sorted(snapshot.channels.values(), key=lambda c: c.id):
                        if c.group_id != target_id:
                            continue
                        name = (
                            c.name if pool.is_event
                            else normalize_key(clean_display_name(c.name, config.token_re))
                        )
                        by_name.setdefault(name, []).append(c)
                channel = next(
                    (
                        c
                        for name in entry.name_keys
                        for c in by_name.get(name, [])
                        if c.id not in claimed
                    ),
                    None,
                )
            pool.channels[key] = channel
            if channel is not None:
                claimed.add(channel.id)
    return claimed


def _plan_deletions(pools, config, snapshot, state, now, warnings):
    """Orphans (remembered keys gone from the provider) and stale events.
    Returns (state, [(pool_id, key, ChannelInfo, reason)])."""
    channel_by_uuid = {c.uuid: c for c in snapshot.channels.values()}
    claimed = {c.id for p in pools for c in p.channels.values() if c is not None}
    deletions = []
    configured = {r.pool_id for r in config.rules + config.event_rules}
    state = state.prune_to(configured)  # rule removed: keep its channels
    for pool in pools:
        pool_id = pool.pool_id
        if pool.is_event and not pool.entries:
            # Events have no grace period: an empty group (failed refresh,
            # streams flagged stale) must not wipe the whole block.
            continue
        current = set(pool.entries)
        for key in state.remembered_keys(pool_id):
            if key in current:
                state = state.mark_present(pool_id, key)
                continue
            channel = channel_by_uuid.get(state.uuid_for(pool_id, key))
            if channel is None or channel.id in claimed:
                # Gone, or still mapped under another key (e.g. after a
                # normalization change): never delete, just forget.
                state = state.forget(pool_id, key)
                continue
            if pool.is_event:
                # Event streams never come back; no grace period.
                deletions.append((pool_id, key, channel, "event gone from provider"))
                continue
            days = state.days_missing(pool_id, key, now)
            if days is None:
                state = state.mark_missing(pool_id, key, now)
                warnings.append(
                    f"'{channel.name}' (#{channel.number:g}) gone from provider, "
                    f"deleting after {config.grace_days} day(s) if it stays gone"
                )
                continue
            if days >= config.grace_days:
                deletions.append((
                    pool_id, key, channel,
                    f"gone from provider for >= {config.grace_days} day(s)",
                ))
    # Stale events: started more than stale_hours ago, delete regardless of
    # whether the provider still lists them.
    for pool in pools:
        if not pool.is_event:
            continue
        for key in pool.stale:
            channel = pool.channels.get(key)
            if channel is not None:
                deletions.append((
                    pool.pool_id, key, channel,
                    f"event started more than {config.stale_hours:g} hour(s) ago",
                ))
            else:
                state = state.forget(pool.pool_id, key)
    return state, deletions


def _assign_numbers(pools, snapshot, deletions, repack, warnings):
    """Numbers for new channels (and, on a repack, for existing event
    channels). Every existing number is occupied; deletions free theirs.
    Returns [(pool, key, number, foreign_skips)]."""
    used = {c.number for c in snapshot.channels.values()}
    deleted_ids = set()
    for _pid, _key, channel, _reason in deletions:
        used.discard(channel.number)
        deleted_ids.add(channel.id)
    ours = {c.number for p in pools for c in p.channels.values() if c is not None}
    creates = []
    if repack:
        # Event blocks are re-packed in chronological order on the first run
        # of each server-local day; later runs only fill free slots.
        for pool in pools:
            if not pool.is_event:
                continue
            for key in pool.active:
                channel = pool.channels.get(key)
                if channel is not None and channel.id not in deleted_ids:
                    used.discard(channel.number)
            number = float(pool.rule.start)
            for key in pool.active:
                skipped = 0
                while number in used:
                    skipped += 1
                    number += 1
                if skipped:
                    warnings.append(
                        f"'{pool.entries[key].name}': skipped {skipped} foreign-occupied "
                        f"number(s), landed on {number:g}"
                    )
                used.add(number)
                ours.add(number)
                if pool.channels.get(key) is None:
                    creates.append((pool, key, number, skipped))
                else:
                    pool.numbers[key] = number
                number += 1
    for pool in pools:
        if repack and pool.is_event:
            continue
        number = float(pool.rule.start)
        for key in pool.active:
            if pool.channels.get(key) is not None:
                continue
            skipped = 0
            while number in used:
                if number not in ours:
                    skipped += 1
                number += 1
            used.add(number)
            creates.append((pool, key, number, skipped))
            if skipped:
                warnings.append(
                    f"'{pool.entries[key].name}': skipped {skipped} foreign-occupied "
                    f"number(s), landed on {number:g}"
                )
            number += 1
    return creates


def _link_changes(existing_ids, wanted_ids):
    """Link ops needed to turn the existing ordered links into the wanted ones."""
    changes = sum(1 for sid in existing_ids if sid not in wanted_ids)
    existing_order = {sid: order for order, sid in enumerate(existing_ids)}
    for order, sid in enumerate(wanted_ids):
        if existing_order.get(sid) != order:
            changes += 1
    return changes


def _plan_actions(pools, snapshot, state, creates, deletions):
    actions = []
    summary = []
    created_groups = set()
    for pool in pools:
        pool_id = pool.pool_id
        pool_created = pool_updated = 0
        if pool.target_name not in snapshot.group_ids and pool.target_name not in created_groups:
            actions.append(CreateGroup(pool.target_name))
            created_groups.add(pool.target_name)

        for key in pool.active:
            entry = pool.entries[key]
            channel = pool.channels.get(key)
            if channel is None:
                continue
            state = state.remember(pool_id, key, channel.uuid)
            fields = {}
            tvg_id = entry.streams[0].tvg_id
            if tvg_id:
                if channel.tvg_id != tvg_id:
                    fields["tvg_id"] = tvg_id
                epg_id = snapshot.epg_ids.get(tvg_id)
                if epg_id is not None and channel.epg_data_id != epg_id:
                    fields["epg_data"] = epg_id
            if pool.is_event:
                if channel.name != entry.name:
                    fields["name"] = entry.name
                number = pool.numbers.get(key)
                if number is not None and channel.number != number:
                    fields["channel_number"] = number
            stream_ids = tuple(s.id for s in entry.streams)
            stream_changes = _link_changes(snapshot.links.get(channel.id, ()), stream_ids)
            if fields or stream_changes:
                pool_updated += 1
                actions.append(UpdateChannel(
                    channel_id=channel.id,
                    name=fields.get("name", channel.name),
                    number=fields.get("channel_number", channel.number),
                    fields=fields,
                    stream_ids=stream_ids,
                    stream_changes=stream_changes,
                ))

        for cpool, key, number, _skipped in creates:
            if cpool is not pool:
                continue
            entry = pool.entries[key]
            primary = entry.streams[0]
            pool_created += 1
            actions.append(CreateChannel(
                pool_id=pool_id,
                key=key,
                number=number,
                name=entry.name,
                group_name=pool.target_name,
                tvg_id=primary.tvg_id,
                epg_id=snapshot.epg_ids.get(primary.tvg_id) if primary.tvg_id else None,
                logo_url=primary.logo_url,
                stream_ids=tuple(s.id for s in entry.streams),
            ))

        group_names = ", ".join(g for _a, g in pool.rule.groups)
        summary.append(f"{group_names}: {pool_created} created, {pool_updated} updated")

    for pool_id, key, channel, reason in deletions:
        actions.append(DeleteChannel(channel.id, channel.name, channel.number, reason))
        state = state.forget(pool_id, key)
    return actions, state, summary
