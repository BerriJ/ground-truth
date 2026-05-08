"""Compute structured diffs between two snapshots of events."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class FloorChange:
    floor: str
    artists_added: list[str] = field(default_factory=list)
    artists_removed: list[str] = field(default_factory=list)


@dataclass
class Change:
    kind: str  # "added" | "cancelled" | "modified"
    id: str
    date_iso: str | None
    date_label: str | None
    title: str | None
    url: str | None
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    floors_added: list[str] = field(default_factory=list)
    floors_removed: list[str] = field(default_factory=list)
    floor_changes: list[FloorChange] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_SCALAR_FIELDS = ("date_iso", "date_label", "time", "category", "title")


def _floors_map(event: dict[str, Any]) -> dict[str, list[str]]:
    return {f["name"]: list(f["artists"]) for f in event.get("floors", [])}


def _index(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in events}


def compute(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    today: date,
) -> list[Change]:
    """Return a list of meaningful changes between two snapshots.

    `old` and `new` are lists of event dicts (as serialized by `Event.to_dict`).
    Removals of events whose `date_iso` is strictly before `today` are
    suppressed (they are simply rolling off the homepage).
    """
    old_idx = _index(old)
    new_idx = _index(new)
    changes: list[Change] = []

    today_str = today.isoformat()

    for ev_id, ev in new_idx.items():
        if ev_id not in old_idx:
            changes.append(_make_added(ev))

    for ev_id, ev in old_idx.items():
        if ev_id in new_idx:
            continue
        if ev.get("date_iso") and ev["date_iso"] < today_str:
            continue  # past event silently rolling off
        changes.append(_make_cancelled(ev))

    for ev_id, new_ev in new_idx.items():
        old_ev = old_idx.get(ev_id)
        if old_ev is None:
            continue
        change = _diff_event(old_ev, new_ev)
        if change is not None:
            changes.append(change)

    changes.sort(key=lambda c: (c.date_iso or "", c.id, c.kind))
    return changes


def _make_added(ev: dict[str, Any]) -> Change:
    return Change(
        kind="added",
        id=ev["id"],
        date_iso=ev.get("date_iso"),
        date_label=ev.get("date_label"),
        title=ev.get("title"),
        url=ev.get("url"),
    )


def _make_cancelled(ev: dict[str, Any]) -> Change:
    return Change(
        kind="cancelled",
        id=ev["id"],
        date_iso=ev.get("date_iso"),
        date_label=ev.get("date_label"),
        title=ev.get("title"),
        url=ev.get("url"),
    )


def _diff_event(old: dict[str, Any], new: dict[str, Any]) -> Change | None:
    fields_diff: dict[str, dict[str, Any]] = {}

    for key in _SCALAR_FIELDS:
        if old.get(key) != new.get(key):
            fields_diff[key] = {"old": old.get(key), "new": new.get(key)}

    old_ticket = old.get("ticket") or {"state": "none", "url": None}
    new_ticket = new.get("ticket") or {"state": "none", "url": None}
    if old_ticket.get("state") != new_ticket.get("state"):
        fields_diff["ticket_state"] = {
            "old": old_ticket.get("state"),
            "new": new_ticket.get("state"),
        }
    elif old_ticket.get("url") != new_ticket.get("url") and new_ticket.get("state") != "none":
        fields_diff["ticket_url"] = {
            "old": old_ticket.get("url"),
            "new": new_ticket.get("url"),
        }

    old_floors = _floors_map(old)
    new_floors = _floors_map(new)

    floors_added = [name for name in new_floors if name not in old_floors]
    floors_removed = [name for name in old_floors if name not in new_floors]
    floor_changes: list[FloorChange] = []
    for name in old_floors.keys() & new_floors.keys():
        old_artists = old_floors[name]
        new_artists = new_floors[name]
        if old_artists == new_artists:
            continue
        old_set = set(old_artists)
        new_set = set(new_artists)
        added = [a for a in new_artists if a not in old_set]
        removed = [a for a in old_artists if a not in new_set]
        if added or removed:
            floor_changes.append(
                FloorChange(floor=name, artists_added=added, artists_removed=removed)
            )

    if not (fields_diff or floors_added or floors_removed or floor_changes):
        return None

    return Change(
        kind="modified",
        id=new["id"],
        date_iso=new.get("date_iso"),
        date_label=new.get("date_label"),
        title=new.get("title"),
        url=new.get("url"),
        fields=fields_diff,
        floors_added=floors_added,
        floors_removed=floors_removed,
        floor_changes=floor_changes,
    )
