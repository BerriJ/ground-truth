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
class SlotChange:
    """A change to a single artist slot (time and/or bio)."""

    floor: str
    name: str
    time_old: str | None = None
    time_new: str | None = None
    bio_changed: bool = False


@dataclass
class FloorSubtitleChange:
    floor: str
    old: str | None
    new: str | None


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
    slot_changes: list[SlotChange] = field(default_factory=list)
    floor_subtitle_changes: list[FloorSubtitleChange] = field(default_factory=list)
    description: dict[str, Any] | None = None  # {"old": ..., "new": ...}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_SCALAR_FIELDS = ("date_iso", "date_label", "time", "category", "title")


def _floors_map(event: dict[str, Any]) -> dict[str, list[str]]:
    return {f["name"]: list(f["artists"]) for f in event.get("floors", [])}


def _detail_floors_map(
    event: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return ``{floor_name: {"subtitle": str|None, "slots": {name: slot_dict}}}``."""
    detail = event.get("detail")
    if not detail:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for floor in detail.get("floors", []) or []:
        slots = {s["name"]: s for s in floor.get("slots", []) or []}
        out[floor["name"]] = {
            "subtitle": floor.get("subtitle"),
            "slots": slots,
        }
    return out


def _index(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in events}


def compute(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    today: date,
) -> list[Change]:
    """Return a list of meaningful changes between two snapshots."""
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

    # Detail-level diffs (slot times, bios, descriptions, floor subtitles).
    slot_changes: list[SlotChange] = []
    floor_subtitle_changes: list[FloorSubtitleChange] = []
    description_change: dict[str, Any] | None = None

    old_detail = old.get("detail")
    new_detail = new.get("detail")
    if old_detail and new_detail:
        old_desc = old_detail.get("description")
        new_desc = new_detail.get("description")
        if old_desc != new_desc:
            description_change = {"old": old_desc, "new": new_desc}

        old_dfloors = _detail_floors_map(old)
        new_dfloors = _detail_floors_map(new)
        for fname in old_dfloors.keys() & new_dfloors.keys():
            of = old_dfloors[fname]
            nf = new_dfloors[fname]
            if of.get("subtitle") != nf.get("subtitle"):
                floor_subtitle_changes.append(
                    FloorSubtitleChange(
                        floor=fname, old=of.get("subtitle"), new=nf.get("subtitle")
                    )
                )
            for slot_name in of["slots"].keys() & nf["slots"].keys():
                old_slot = of["slots"][slot_name]
                new_slot = nf["slots"][slot_name]
                t_old = old_slot.get("time")
                t_new = new_slot.get("time")
                b_old = old_slot.get("bio")
                b_new = new_slot.get("bio")
                if t_old == t_new and b_old == b_new:
                    continue
                slot_changes.append(
                    SlotChange(
                        floor=fname,
                        name=slot_name,
                        time_old=t_old if t_old != t_new else None,
                        time_new=t_new if t_old != t_new else None,
                        bio_changed=b_old != b_new,
                    )
                )

    if not (
        fields_diff
        or floors_added
        or floors_removed
        or floor_changes
        or slot_changes
        or floor_subtitle_changes
        or description_change
    ):
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
        slot_changes=slot_changes,
        floor_subtitle_changes=floor_subtitle_changes,
        description=description_change,
    )
