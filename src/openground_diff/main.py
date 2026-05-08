"""CLI orchestrator: scrape -> diff -> persist -> render."""
from __future__ import annotations

import argparse
import json
import sys
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
    args = parser.parse_args(argv)

    if args.from_file:
        html = args.from_file.read_text(encoding="utf-8")
    else:
        html = scrape.fetch()

    events = scrape.parse_html(html)
    new_events = _events_to_json(events)

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    run_at = now_utc.isoformat()
    today_berlin: date = now_utc.astimezone(BERLIN).date()

    current_path = args.data_dir / "current.json"
    history_path = args.data_dir / "history.jsonl"

    old_events = _load_current(current_path)
    changes = compute(old_events, new_events, today_berlin)

    is_first_run = not current_path.exists()

    _write_current(current_path, run_at, new_events)

    change_dicts = [asdict(c) for c in changes]
    if change_dicts and not is_first_run:
        _append_history(history_path, run_at, change_dicts)

    if not args.no_render:
        render_site(history_path, args.site_dir)

    print(
        f"scraped {len(new_events)} events, "
        f"{len(changes)} change(s){' [initial run, not logged]' if is_first_run else ''}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
