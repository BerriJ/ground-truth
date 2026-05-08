from openground_diff.notify import format_changes


def test_format_added_and_cancelled():
    changes = [
        {
            "kind": "added",
            "id": "2026-06-01-clubnight",
            "date_iso": "2026-06-01",
            "date_label": "So.01.06.26",
            "title": "Clubnight",
            "url": "https://www.openground.club/de/schedule/2026-06-01-clubnight",
            "fields": {},
            "floors_added": [],
            "floors_removed": [],
            "floor_changes": [],
        },
        {
            "kind": "cancelled",
            "id": "2026-06-08-x",
            "date_iso": "2026-06-08",
            "date_label": "So.08.06.26",
            "title": "X",
            "url": None,
            "fields": {},
            "floors_added": [],
            "floors_removed": [],
            "floor_changes": [],
        },
    ]
    text, html = format_changes(changes, run_at="2026-05-08T12:00:00+00:00")
    assert "2 change(s)" in text
    assert "[Added] Clubnight" in text
    assert "[Cancelled] X" in text
    assert "<strong>Open Ground</strong>" in html
    assert '<a href="https://www.openground.club/de/schedule/2026-06-01-clubnight">Clubnight</a>' in html
    assert "[Cancelled]" in html


def test_format_modified_with_fields_and_floors():
    changes = [
        {
            "kind": "modified",
            "id": "e1",
            "date_iso": "2026-06-01",
            "date_label": "So.01.06.26",
            "title": "Clubnight",
            "url": "https://example.org/e1",
            "fields": {
                "time": {"old": "20:00", "new": "22:00"},
                "ticket_state": {"old": "onsale", "new": "soldout"},
            },
            "floors_added": ["ANNEX"],
            "floors_removed": [],
            "floor_changes": [
                {
                    "floor": "FREIFELD",
                    "artists_added": ["C"],
                    "artists_removed": ["B"],
                }
            ],
        }
    ]
    text, html = format_changes(changes, run_at="2026-05-08T12:00:00+00:00",
                                site_url="https://example.org/site/")
    assert "time: 20:00 → 22:00" in text
    assert "ticket_state: onsale → soldout" in text
    assert "Floor added: ANNEX" in text
    assert "FREIFELD: + C" in text
    assert "FREIFELD: − B" in text
    assert "time: 20:00 → 22:00" in html
    assert "FREIFELD: + C" in html
    assert 'href="https://example.org/site/"' in html


def test_html_escapes_title():
    changes = [
        {
            "kind": "added",
            "id": "x",
            "date_iso": "2026-06-01",
            "date_label": "So.01.06.26",
            "title": "Rock & <Roll>",
            "url": None,
            "fields": {},
            "floors_added": [],
            "floors_removed": [],
            "floor_changes": [],
        }
    ]
    _, html = format_changes(changes, run_at="2026-05-08T12:00:00+00:00")
    assert "Rock &amp; &lt;Roll&gt;" in html
    assert "<Roll>" not in html
