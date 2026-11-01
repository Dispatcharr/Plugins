"""Mapping state: what the plugin remembers between runs. An immutable value;
every mutator returns a new MappingState. No Django imports.

On disk (state.json):
    {"pools": {pool_id: {key: {"uuid": str, "missing_since": iso | null}}},
     "event_repack_date": "YYYY-MM-DD"}
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, replace
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MappingState:
    # pool_id -> {key: (uuid, missing_since_iso_or_None)}
    pools: dict = field(default_factory=dict)
    event_repack_date: str | None = None

    # --- queries ---------------------------------------------------------

    def uuid_for(self, pool_id, key):
        entry = self.pools.get(pool_id, {}).get(key)
        return entry[0] if entry else None

    def uuids(self):
        """Every channel uuid remembered in any pool."""
        return frozenset(
            uuid for pool in self.pools.values() for uuid, _m in pool.values() if uuid
        )

    def remembered_keys(self, pool_id):
        return tuple(self.pools.get(pool_id, {}))

    def days_missing(self, pool_id, key, now):
        """Whole days since the key was marked missing; None when it is not
        marked, or the stored timestamp is unreadable."""
        entry = self.pools.get(pool_id, {}).get(key)
        if not entry or not entry[1]:
            return None
        try:
            return (now - datetime.fromisoformat(entry[1])).days
        except (ValueError, TypeError):
            return None

    def repack_due(self, today):
        return self.event_repack_date != today.isoformat()

    # --- mutators (return a new state) -----------------------------------

    def remember(self, pool_id, key, uuid):
        """Key is mapped to this channel; clears any missing timer."""
        return self._with(pool_id, key, (uuid, None))

    def mark_present(self, pool_id, key):
        """Key is present again; clears the missing timer. No-op when the
        key is not remembered."""
        entry = self.pools.get(pool_id, {}).get(key)
        if not entry or entry[1] is None:
            return self
        return self._with(pool_id, key, (entry[0], None))

    def mark_missing(self, pool_id, key, now):
        """Start the missing timer unless a readable one is already running."""
        entry = self.pools.get(pool_id, {}).get(key)
        if not entry or self.days_missing(pool_id, key, now) is not None:
            return self
        return self._with(pool_id, key, (entry[0], now.isoformat()))

    def forget(self, pool_id, key):
        pool = self.pools.get(pool_id)
        if not pool or key not in pool:
            return self
        new_pool = {k: v for k, v in pool.items() if k != key}
        pools = {p: v for p, v in self.pools.items() if p != pool_id}
        if new_pool:
            pools[pool_id] = new_pool
        return replace(self, pools=pools)

    def prune_to(self, pool_ids):
        """Drop every pool whose rule is gone from the config."""
        return replace(self, pools={p: v for p, v in self.pools.items() if p in pool_ids})

    def mark_repacked(self, today):
        return replace(self, event_repack_date=today.isoformat())

    def _with(self, pool_id, key, entry):
        pools = dict(self.pools)
        pools[pool_id] = {**pools.get(pool_id, {}), key: entry}
        return replace(self, pools=pools)

    # --- serialisation ---------------------------------------------------

    def to_dict(self):
        data = {
            "pools": {
                pool_id: {
                    key: {"uuid": uuid, "missing_since": missing}
                    for key, (uuid, missing) in pool.items()
                }
                for pool_id, pool in self.pools.items()
            }
        }
        if self.event_repack_date is not None:
            data["event_repack_date"] = self.event_repack_date
        return data

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or not isinstance(data.get("pools"), dict):
            return cls()
        pools = {}
        for pool_id, pool in data["pools"].items():
            if not isinstance(pool, dict):
                continue
            pools[pool_id] = {
                key: (info.get("uuid"), info.get("missing_since"))
                for key, info in pool.items()
                if isinstance(info, dict)
            }
        repack = data.get("event_repack_date")
        return cls(pools=pools, event_repack_date=repack if isinstance(repack, str) else None)


def load_state(path):
    """Read state.json; a missing or unreadable file is an empty state."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return MappingState.from_dict(json.load(fh))
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"automap-channelarr: could not read state file {path}: {e}")
    return MappingState()


def save_state(path, state):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state.to_dict(), fh, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning(f"automap-channelarr: could not write state file {path}: {e}")
