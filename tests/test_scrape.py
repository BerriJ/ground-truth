from pathlib import Path

from openground_diff.scrape import parse_html

FIXTURE = Path(__file__).resolve().parents[1] / "Open Ground.html"


def _by_id(events):
    return {e.id: e for e in events}


def test_parses_known_events():
    html = FIXTURE.read_text(encoding="utf-8")
    events = parse_html(html)
    assert len(events) >= 10

    by_id = _by_id(events)
    # 2026-05-09 Abyss event: weeztix link, full FREIFELD line-up
    abyss = by_id["2026-05-09-abyss-at-open-ground"]
    assert abyss.date_iso == "2026-05-09"
    assert abyss.category == "Extended Clubnight"
    assert abyss.time == "20:00–07:00"
    assert abyss.title == "Abyss at Open Ground"
    assert abyss.ticket.state == "onsale"
    assert abyss.ticket.url and abyss.ticket.url.startswith("https://shop.weeztix.com/")
    floor_names = [f.name for f in abyss.floors]
    assert floor_names == ["FREIFELD", "ANNEX"]
    freifeld = abyss.floors[0]
    assert "Kā (live) Gong x Synthesis" in freifeld.artists
    assert "dBridge" in freifeld.artists
    assert "Nono Gigsta" in freifeld.artists
    annex = abyss.floors[1]
    assert annex.artists == ["Andy Martin", "Mama Snake", "Basic Chanel (ambient set)"]


def test_soldout_event():
    html = FIXTURE.read_text(encoding="utf-8")
    by_id = _by_id(parse_html(html))
    ev = by_id["2026-05-23"]
    assert ev.ticket.state == "soldout"
    assert ev.ticket.url is None
    floors = {f.name: f.artists for f in ev.floors}
    assert floors["FREIFELD"] == [
        "Zoë Mc Pherson",
        "Rob Smith",
        "Toumba",
        "Skrillex",
        "Josi Devil",
    ]
    assert floors["ANNEX"] == ["Hans Nieswandt", "Uh-Young Kim"]


def test_free_event():
    html = FIXTURE.read_text(encoding="utf-8")
    by_id = _by_id(parse_html(html))
    # 2026-05-14 and 2026-05-21 / 2026-05-28 are free entry events
    free_ids = {ev.id for ev in by_id.values() if ev.ticket.state == "free"}
    assert free_ids  # at least one free event
    assert "2026-05-14" in free_ids


def test_no_duplicates():
    html = FIXTURE.read_text(encoding="utf-8")
    events = parse_html(html)
    ids = [e.id for e in events]
    assert len(ids) == len(set(ids))


def test_events_sorted_by_date():
    html = FIXTURE.read_text(encoding="utf-8")
    events = parse_html(html)
    dates = [e.date_iso for e in events if e.date_iso]
    assert dates == sorted(dates)
