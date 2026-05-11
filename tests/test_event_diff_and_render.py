import json
from datetime import date
from pathlib import Path

from openground_diff.diff import compute
from openground_diff.render import render_site


def _ev_with_detail(id_="e1", floors=None, description="hello"):
    return {
        "id": id_,
        "url": f"https://www.openground.club/en/schedule/{id_}",
        "date_iso": "2026-06-01",
        "date_label": "Mon.01.06.26",
        "time": "22:00–06:00",
        "category": "Clubnight",
        "title": None,
        "floors": [
            {"name": "FREIFELD", "artists": ["Alice", "Bob"]},
        ],
        "ticket": {"state": "onsale", "url": "https://shop/x"},
        "detail": {
            "floors": floors
            or [
                {
                    "name": "FREIFELD",
                    "subtitle": None,
                    "slots": [
                        {
                            "name": "Alice",
                            "time": "23:00",
                            "city": "Berlin",
                            "bio": "Old bio",
                        },
                        {
                            "name": "Bob",
                            "time": "02:00",
                            "city": "Köln",
                            "bio": "Bob bio",
                        },
                    ],
                }
            ],
            "description": description,
        },
    }


TODAY = date(2026, 5, 8)


def test_slot_time_change_detected():
    old = _ev_with_detail()
    new = _ev_with_detail()
    new["detail"]["floors"][0]["slots"][0]["time"] = "01:00"
    changes = compute([old], [new], TODAY)
    assert len(changes) == 1
    sc = changes[0].slot_changes
    assert len(sc) == 1
    assert sc[0].name == "Alice"
    assert sc[0].time_old == "23:00"
    assert sc[0].time_new == "01:00"
    assert sc[0].bio_changed is False


def test_bio_change_detected():
    old = _ev_with_detail()
    new = _ev_with_detail()
    new["detail"]["floors"][0]["slots"][1]["bio"] = "Brand new bio"
    changes = compute([old], [new], TODAY)
    assert len(changes) == 1
    sc = changes[0].slot_changes
    assert sc[0].name == "Bob"
    assert sc[0].bio_changed is True
    assert sc[0].time_old is None and sc[0].time_new is None


def test_description_change_detected():
    old = _ev_with_detail(description="Old description")
    new = _ev_with_detail(description="New description")
    changes = compute([old], [new], TODAY)
    assert changes[0].description == {"old": "Old description", "new": "New description"}


def test_floor_subtitle_change_detected():
    old = _ev_with_detail()
    new = _ev_with_detail()
    new["detail"]["floors"][0]["subtitle"] = "Illusion at Open Ground"
    changes = compute([old], [new], TODAY)
    assert len(changes[0].floor_subtitle_changes) == 1
    fsc = changes[0].floor_subtitle_changes[0]
    assert fsc.floor == "FREIFELD"
    assert fsc.old is None
    assert fsc.new == "Illusion at Open Ground"


def test_render_event_page(tmp_path: Path):
    history = tmp_path / "history.jsonl"
    history.write_text(
        json.dumps(
            {
                "run_at": "2026-05-08T12:00:00+00:00",
                "changes": [
                    {
                        "kind": "modified",
                        "id": "2026-06-01",
                        "date_iso": "2026-06-01",
                        "date_label": "Mon.01.06.26",
                        "title": None,
                        "url": "https://www.openground.club/en/schedule/2026-06-01",
                        "fields": {},
                        "floors_added": [],
                        "floors_removed": [],
                        "floor_changes": [],
                        "slot_changes": [
                            {
                                "floor": "FREIFELD",
                                "name": "Alice",
                                "time_old": "23:00",
                                "time_new": "01:00",
                                "bio_changed": False,
                            }
                        ],
                        "floor_subtitle_changes": [],
                        "description": {"old": "Old", "new": "New"},
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    current = tmp_path / "current.json"
    current.write_text(
        json.dumps(
            {
                "scraped_at": "2026-05-08T12:00:00+00:00",
                "events": [_ev_with_detail(id_="2026-06-01")],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "site"
    render_site(history, out, current_path=current)

    index = (out / "index.html").read_text(encoding="utf-8")
    # Title link points at local event page, not openground.club
    assert 'href="event/2026-06-01.html"' in index

    event_page = (out / "event" / "2026-06-01.html").read_text(encoding="utf-8")
    assert "Alice" in event_page
    assert "23:00" in event_page  # in change log
    assert "01:00" in event_page  # in change log
    assert "openground.club/en/schedule/2026-06-01" in event_page
    assert "About the night" in event_page
