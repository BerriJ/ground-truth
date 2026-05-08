from datetime import date

from openground_diff.diff import compute


def _ev(
    id_: str,
    date_iso: str = "2026-06-01",
    floors=None,
    ticket=None,
    time="20:00–06:00",
    category="Clubnight",
    title=None,
    date_label="So.01.06.26",
):
    return {
        "id": id_,
        "url": f"https://www.openground.club/de/schedule/{id_}",
        "date_iso": date_iso,
        "date_label": date_label,
        "time": time,
        "category": category,
        "title": title,
        "floors": floors or [
            {"name": "FREIFELD", "artists": ["A", "B"]},
            {"name": "ANNEX", "artists": ["X"]},
        ],
        "ticket": ticket or {"state": "onsale", "url": "https://shop.weeztix.com/abc"},
    }


TODAY = date(2026, 5, 8)


def test_no_changes():
    snap = [_ev("e1")]
    assert compute(snap, snap, TODAY) == []


def test_added_event():
    changes = compute([], [_ev("e1")], TODAY)
    assert len(changes) == 1
    assert changes[0].kind == "added"
    assert changes[0].id == "e1"


def test_past_removal_suppressed():
    old = [_ev("past", date_iso="2026-05-01")]
    changes = compute(old, [], TODAY)
    assert changes == []


def test_future_removal_is_cancellation():
    old = [_ev("future", date_iso="2026-06-15")]
    changes = compute(old, [], TODAY)
    assert len(changes) == 1
    assert changes[0].kind == "cancelled"
    assert changes[0].id == "future"


def test_ticket_state_change():
    old = [_ev("e1", ticket={"state": "onsale", "url": "https://shop/x"})]
    new = [_ev("e1", ticket={"state": "soldout", "url": None})]
    changes = compute(old, new, TODAY)
    assert len(changes) == 1
    c = changes[0]
    assert c.kind == "modified"
    assert c.fields == {"ticket_state": {"old": "onsale", "new": "soldout"}}


def test_ticket_url_change_only():
    old = [_ev("e1", ticket={"state": "onsale", "url": "https://shop/a"})]
    new = [_ev("e1", ticket={"state": "onsale", "url": "https://shop/b"})]
    changes = compute(old, new, TODAY)
    assert len(changes) == 1
    assert "ticket_url" in changes[0].fields


def test_artist_added_and_removed():
    old = [_ev("e1", floors=[
        {"name": "FREIFELD", "artists": ["A", "B"]},
        {"name": "ANNEX", "artists": ["X"]},
    ])]
    new = [_ev("e1", floors=[
        {"name": "FREIFELD", "artists": ["A", "C"]},
        {"name": "ANNEX", "artists": ["X"]},
    ])]
    changes = compute(old, new, TODAY)
    assert len(changes) == 1
    fc = changes[0].floor_changes
    assert len(fc) == 1
    assert fc[0].floor == "FREIFELD"
    assert fc[0].artists_added == ["C"]
    assert fc[0].artists_removed == ["B"]


def test_floor_added_and_removed():
    old = [_ev("e1", floors=[{"name": "FREIFELD", "artists": ["A"]}])]
    new = [_ev("e1", floors=[
        {"name": "FREIFELD", "artists": ["A"]},
        {"name": "ANNEX", "artists": ["Z"]},
    ])]
    changes = compute(old, new, TODAY)
    assert len(changes) == 1
    assert changes[0].floors_added == ["ANNEX"]
    assert changes[0].floors_removed == []


def test_time_change():
    old = [_ev("e1", time="20:00–06:00")]
    new = [_ev("e1", time="22:00–06:00")]
    changes = compute(old, new, TODAY)
    assert len(changes) == 1
    assert changes[0].fields["time"] == {"old": "20:00–06:00", "new": "22:00–06:00"}
