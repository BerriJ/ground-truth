from pathlib import Path

import pytest

from openground_diff.scrape import parse_event_detail

FIXTURE = Path(__file__).resolve().parents[1] / "specific_day.html"

pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="specific_day.html fixture not present"
)


def test_parse_event_detail_floors_and_slots():
    html = FIXTURE.read_text(encoding="utf-8")
    detail = parse_event_detail(html)

    assert len(detail.floors) == 2
    freifeld, annex = detail.floors

    assert freifeld.name == "FREIFELD"
    assert freifeld.subtitle in (None, "")
    slot_names = [s.name for s in freifeld.slots]
    assert slot_names == ["Marcus Worgull", "Michael Mayer"]
    assert freifeld.slots[0].time == "23:30"
    assert freifeld.slots[0].city == "Cologne"
    assert freifeld.slots[0].bio is not None
    assert "Innervisions" in freifeld.slots[0].bio

    assert annex.name == "ANNEX"
    assert annex.subtitle == "Illusion at Open Ground"
    annex_names = [s.name for s in annex.slots]
    assert annex_names == ["Ada Luvv", "FEELX", "Magnus b2b Ole B/P"]
    assert annex.slots[0].time == "22:00"
    # Last slot has two bios (Magnus + Ole B/P) joined
    last_bio = annex.slots[-1].bio or ""
    assert "Magnus is a DJ from Cologne" in last_bio
    assert "Ole B/P is a Wuppertal-born" in last_bio


def test_parse_event_detail_description():
    html = FIXTURE.read_text(encoding="utf-8")
    detail = parse_event_detail(html)
    assert detail.description is not None
    assert "deep, forward-thinking club music" in detail.description
    assert "Admission 20" in detail.description
