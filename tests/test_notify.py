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
    assert "🟩 Clubnight" in text  # added marker
    assert "🟥 X" in text  # cancelled marker
    assert '<a href="https://www.openground.club/de/schedule/2026-06-01-clubnight">Clubnight</a>' in html
    assert "🟥" in html  # cancelled marker present in html too
    # Header line is no longer rendered.
    assert "Open Ground" not in text
    assert "Open Ground" not in html
    assert "change(s)" not in text


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
    # When site_url is set, the headline links to our per-event page rather
    # than upstream openground.club.
    assert 'href="https://example.org/site/event/e1.html"' in html
    assert "https://example.org/e1" not in html


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


def test_kind_color_bars_and_single_headline():
    changes = [
        {
            "kind": "added",
            "id": "2026-06-01",
            "date_iso": "2026-06-01",
            "date_label": "So.01.06.26",
            "title": None,
            "url": "https://x/y",
            "fields": {},
            "floors_added": [],
            "floors_removed": [],
            "floor_changes": [],
        },
        {
            "kind": "cancelled",
            "id": "2026-06-08",
            "date_iso": "2026-06-08",
            "date_label": "So.08.06.26",
            "title": "X",
            "url": None,
            "fields": {},
            "floors_added": [],
            "floors_removed": [],
            "floor_changes": [],
        },
        {
            "kind": "modified",
            "id": "2026-06-15",
            "date_iso": "2026-06-15",
            "date_label": "Mo.15.06.26",
            "title": None,
            "url": "https://x/z",
            "fields": {"time": {"old": "20:00", "new": "22:00"}},
            "floors_added": [],
            "floors_removed": [],
            "floor_changes": [],
        },
    ]
    text, html = format_changes(changes, run_at="2026-05-08T12:00:00+00:00")
    # Per-kind colored emoji markers (Unicode, render on every client).
    assert "🟩" in html  # added
    assert "🟥" in html  # cancelled
    assert "🟧" in html  # modified
    # Title-less change uses the date_label as headline, not "id · date_label".
    assert ">So.01.06.26<" in html  # link text for added entry
    # "X" title is used when present; date_label is *not* appended.
    assert "🟥 X</div>" in html
    assert "X · So.08.06.26" not in html
    assert "X · So.08.06.26" not in text
    # The titled cancelled change shows only its title in the text head.
    assert "🟥 X" in text
    assert "🟥 X ·" not in text


def test_slot_change_suppressed_for_newly_added_artist():
    """Bio/time changes for an artist who was just added (or removed) on the
    same floor are noise and should not be reported."""
    changes = [
        {
            "kind": "modified",
            "id": "e1",
            "date_iso": "2026-06-01",
            "date_label": "So.01.06.26",
            "title": None,
            "url": None,
            "fields": {},
            "floors_added": [],
            "floors_removed": [],
            "floor_changes": [
                {
                    "floor": "FREIFELD",
                    "artists_added": ["NewOne"],
                    "artists_removed": ["GoneOne"],
                }
            ],
            "slot_changes": [
                {
                    "floor": "FREIFELD",
                    "name": "NewOne",
                    "time_old": None,
                    "time_new": None,
                    "bio_changed": True,
                },
                {
                    "floor": "FREIFELD",
                    "name": "GoneOne",
                    "time_old": "20:00",
                    "time_new": None,
                    "bio_changed": False,
                },
                {
                    "floor": "FREIFELD",
                    "name": "Stayer",
                    "time_old": "21:00",
                    "time_new": "22:00",
                    "bio_changed": False,
                },
            ],
        }
    ]
    text, html = format_changes(changes, run_at="2026-05-08T12:00:00+00:00")
    assert "FREIFELD: + NewOne" in text
    assert "FREIFELD: − GoneOne" in text
    assert "NewOne: bio updated" not in text
    assert "GoneOne:" not in text or "− GoneOne" in text
    # The genuine slot change for a continuing artist still shows up.
    assert "FREIFELD · Stayer" in text
    assert "NewOne: bio updated" not in html
    assert "Stayer" in html
