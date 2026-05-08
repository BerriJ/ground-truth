import json
from pathlib import Path

from openground_diff.render import render_site


def test_render_writes_index_and_css(tmp_path: Path):
    history = tmp_path / "history.jsonl"
    history.write_text(
        json.dumps(
            {
                "run_at": "2026-05-08T12:00:00+00:00",
                "changes": [
                    {
                        "kind": "added",
                        "id": "2026-06-15",
                        "date_iso": "2026-06-15",
                        "date_label": "Mo.15.06.26",
                        "title": "Some Night",
                        "url": "https://www.openground.club/de/schedule/2026-06-15",
                        "fields": {},
                        "floors_added": [],
                        "floors_removed": [],
                        "floor_changes": [],
                    },
                    {
                        "kind": "modified",
                        "id": "2026-05-23",
                        "date_iso": "2026-05-23",
                        "date_label": "Sa.23.05.26",
                        "title": None,
                        "url": "https://www.openground.club/de/schedule/2026-05-23",
                        "fields": {"ticket_state": {"old": "onsale", "new": "soldout"}},
                        "floors_added": [],
                        "floors_removed": [],
                        "floor_changes": [
                            {"floor": "FREIFELD", "artists_added": ["NewArtist"], "artists_removed": ["OldArtist"]}
                        ],
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "site"
    render_site(history, out)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "Some Night" in index
    assert "added" in index
    assert "ticket_state" in index
    assert "NewArtist" in index
    assert "OldArtist" in index
    assert (out / "style.css").exists()


def test_render_empty_history(tmp_path: Path):
    out = tmp_path / "site"
    render_site(tmp_path / "history.jsonl", out)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "No scrapes yet" in index
