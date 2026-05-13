"""Tests for the sidebar parser and event merging."""
from __future__ import annotations

from datetime import date
from textwrap import dedent

from openground_diff.diff import compute
from openground_diff.main import _filter_past_additions, _merge_events
from openground_diff.scrape import parse_sidebar


SIDEBAR_HTML = dedent(
    """
    <div class="schedule">
        <a href="/en/schedule/2024-06-28-clubnight"
           class="newschedule__item js-openlayer newschedule__item--past">
            <div class="newschedule__top">
                <div class="newschedule__category">Clubnight</div>
                <div class="newschedule__date">Fri.28.06.24</div>
                <div class="newschedule__time">23:00</div>
            </div>
            <div class="newschedule__content">
                <div class="newschedule__title">Clubnight</div>
                <div class="newschedule__floor">
                    <div class="newschedule__floor__label">FREIFELD</div>
                </div>
                <div class="newschedule__artists">Calibre, Breakage, SP:MC</div>
                <div class="newschedule__floor">
                    <div class="newschedule__floor__label">ANNEX</div>
                </div>
                <div class="newschedule__artists">Sedaction</div>
            </div>
        </a>
        <a href="/en/schedule/2026-05-09-abyss-at-open-ground"
           class="newschedule__item js-openlayer newschedule__item--past">
            <div class="newschedule__top">
                <div class="newschedule__category">Extended Clubnight</div>
                <div class="newschedule__date">Sat.09.05.26</div>
                <div class="newschedule__time">20:00–07:00</div>
            </div>
            <div class="newschedule__content">
                <div class="newschedule__title">Abyss at Open Ground</div>
                <div class="newschedule__floor">
                    <div class="newschedule__floor__label">FREIFELD</div>
                </div>
                <div class="newschedule__artists">dBridge, Darwin</div>
            </div>
        </a>
    </div>
    """
)


def test_parse_sidebar_extracts_past_events():
    events = parse_sidebar(SIDEBAR_HTML)
    by_id = {e.id: e for e in events}
    assert "2024-06-28-clubnight" in by_id
    assert "2026-05-09-abyss-at-open-ground" in by_id

    old = by_id["2024-06-28-clubnight"]
    assert old.date_iso == "2024-06-28"
    assert old.date_label == "Fri.28.06.24"
    assert old.time == "23:00"
    assert old.category == "Clubnight"
    assert old.title is None  # title == category collapses to None
    assert [f.name for f in old.floors] == ["FREIFELD", "ANNEX"]
    assert old.floors[0].artists == ["Calibre", "Breakage", "SP:MC"]
    assert old.floors[1].artists == ["Sedaction"]
    assert old.ticket.state == "none"

    abyss = by_id["2026-05-09-abyss-at-open-ground"]
    assert abyss.title == "Abyss at Open Ground"
    assert abyss.floors[0].artists == ["dBridge", "Darwin"]


def _mk(id_: str, date_iso: str, **extra):
    return {
        "id": id_,
        "url": f"https://example.test/{id_}",
        "date_iso": date_iso,
        "date_label": None,
        "time": None,
        "category": None,
        "title": None,
        "floors": [],
        "ticket": {"state": "none", "url": None},
        "detail": None,
        **extra,
    }


def test_merge_prefers_rich_over_old_over_sidebar():
    rich = [_mk("a", "2026-06-01", title="rich")]
    old = [_mk("a", "2026-06-01", title="old"), _mk("b", "2025-01-01", title="old-b")]
    sidebar = [
        _mk("a", "2026-06-01", title="sidebar"),
        _mk("b", "2025-01-01", title="sidebar-b"),
        _mk("c", "2024-01-01", title="sidebar-c"),
    ]
    merged = _merge_events(rich=rich, old=old, sidebar=sidebar)
    by_id = {e["id"]: e for e in merged}
    assert by_id["a"]["title"] == "rich"
    assert by_id["b"]["title"] == "old-b"  # old beats sidebar
    assert by_id["c"]["title"] == "sidebar-c"  # only sidebar has it
    # Sorted by date_iso, id.
    assert [e["id"] for e in merged] == ["c", "b", "a"]


def test_merge_preserves_old_event_dropped_from_new():
    rich: list = []
    sidebar: list = []
    old = [_mk("kept", "2024-01-01")]
    merged = _merge_events(rich=rich, old=old, sidebar=sidebar)
    assert [e["id"] for e in merged] == ["kept"]


def test_filter_past_additions_drops_past_added_only():
    today = date(2026, 5, 13)
    # Use compute() to fabricate change objects.
    new = [_mk("future", "2026-06-01"), _mk("past", "2024-01-01")]
    changes = compute([], new, today)
    kinds_before = {(c.id, c.kind) for c in changes}
    assert ("future", "added") in kinds_before
    assert ("past", "added") in kinds_before

    kept = _filter_past_additions(changes, today)
    kinds_after = {(c.id, c.kind) for c in kept}
    assert ("future", "added") in kinds_after
    assert ("past", "added") not in kinds_after
