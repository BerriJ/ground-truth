"""CLI orchestrator: scrape -> diff -> persist -> render."""
from __future__ import annotations

import argparse
import json
import sys
import time as _time
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import scrape
from .diff import compute
from .render import render_site

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_SITE_DIR = REPO_ROOT / "site"
BERLIN = ZoneInfo("Europe/Berlin")


def _events_to_json(events: list[scrape.Event]) -> list[dict[str, Any]]:
    return [e.to_dict() for e in events]


def _attach_details(events: list[scrape.Event], delay: float = 0.5) -> None:
    """Fetch the per-event page for each event and attach the parsed detail."""
    for i, ev in enumerate(events):
        try:
            html = scrape.fetch_event(ev.id)
            ev.detail = scrape.parse_event_detail(html)
        except Exception as err:  # noqa: BLE001
            print(f"warn: failed to fetch detail for {ev.id}: {err}", file=sys.stderr)
            ev.detail = None
        if delay and i < len(events) - 1:
            _time.sleep(delay)


def _load_current(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("events", [])


def _write_current(path: Path, scraped_at: str, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"scraped_at": scraped_at, "events": events}
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_history(path: Path, run_at: str, changes: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"run_at": run_at, "changes": changes}, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _merge_events(
    *,
    rich: list[dict[str, Any]],
    old: list[dict[str, Any]],
    sidebar: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine snapshots so events are never silently dropped.

    Precedence per event id: freshly-scraped rich block > previously saved
    entry > sidebar summary. This keeps detailed records of events that have
    just rolled off the upcoming list while still backfilling never-before-seen
    past events from the sidebar.
    """
    merged: dict[str, dict[str, Any]] = {}
    for ev in sidebar:
        merged[ev["id"]] = ev
    for ev in old:
        merged[ev["id"]] = ev
    for ev in rich:
        merged[ev["id"]] = ev
    return sorted(merged.values(), key=lambda e: (e.get("date_iso") or "", e["id"]))


def _filter_past_additions(changes: list[Any], today: date) -> list[Any]:
    """Drop ``added`` change entries whose event date is already in the past.

    The sidebar exposes historical events that the scraper has never seen
    before; surfacing them as fresh "added" changes would flood the history
    log on first run without communicating anything new.
    """
    today_str = today.isoformat()
    return [
        c for c in changes
        if not (c.kind == "added" and c.date_iso and c.date_iso < today_str)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-file",
        type=Path,
        help="Read HTML from a local file instead of fetching the live site.",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA_DIR,
        help="Where to read/write current.json and history.jsonl.",
    )
    parser.add_argument(
        "--site-dir", type=Path, default=DEFAULT_SITE_DIR,
        help="Where to write the static site.",
    )
    parser.add_argument(
        "--no-render", action="store_true",
        help="Skip writing the static site (still updates data files).",
    )
    parser.add_argument(
        "--no-details", action="store_true",
        help="Skip fetching per-event detail pages.",
    )
    parser.add_argument(
        "--detail-delay", type=float, default=0.5,
        help="Seconds to sleep between event-detail fetches.",
    )
    args = parser.parse_args(argv)

    if args.from_file:
        html = args.from_file.read_text(encoding="utf-8")
    else:
        html = scrape.fetch()

    events = scrape.parse_html(html)

    if not args.no_details and not args.from_file:
        _attach_details(events, delay=args.detail_delay)

    rich_events = _events_to_json(events)
    sidebar_events = _events_to_json(scrape.parse_sidebar(html))

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    run_at = now_utc.isoformat()
    today_berlin: date = now_utc.astimezone(BERLIN).date()

    current_path = args.data_dir / "current.json"
    history_path = args.data_dir / "history.jsonl"

    is_first_run = not current_path.exists()
    old_events = _load_current(current_path)

    merged_events = _merge_events(
        rich=rich_events, old=old_events, sidebar=sidebar_events
    )
    changes = _filter_past_additions(
        compute(old_events, merged_events, today_berlin), today_berlin
    )

    _write_current(current_path, run_at, merged_events)

    change_dicts = [asdict(c) for c in changes]
    if change_dicts and not is_first_run:
        _append_history(history_path, run_at, change_dicts)

    if not args.no_render:
        render_site(
            history_path,
            args.site_dir,
            last_scrape=run_at,
            current_path=current_path,
        )

    print(
        f"scraped {len(rich_events)} upcoming, {len(sidebar_events)} sidebar, "
        f"{len(merged_events)} total events, "
        f"{len(changes)} change(s){' [initial run, not logged]' if is_first_run else ''}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
