"""Send a synthetic Matrix notification to verify credentials.

Posts a small ``m.text`` message (with HTML formatting) to the configured
Matrix room using the same code path as ``scripts/notify_matrix.py``, but
without touching ``data/history.jsonl`` or the idempotency marker.

Reads the same environment variables as the workflow:

    MATRIX_HOMESERVER   e.g. https://matrix.example.org
    MATRIX_ACCESS_TOKEN bot user's access token
    MATRIX_ROOM_ID      e.g. !abcdef:example.org
    SITE_URL            (optional) included in the test message

Usage::

    python scripts/test_matrix_notify.py            # send the test message
    python scripts/test_matrix_notify.py --dry-run  # only print the payload
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import uuid
from datetime import datetime, timezone

import requests

from openground_diff.notify import format_changes


def _fake_run() -> dict[str, object]:
    """A synthetic run that exercises every change kind."""
    run_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "run_at": run_at,
        "changes": [
            {
                "kind": "added",
                "id": "2099-01-01-test-event",
                "date_iso": "2099-01-01",
                "date_label": "Fr.01.01.99",
                "title": "Matrix notification test",
                "url": "https://www.openground.club/en/schedule/2099-01-01-test-event",
                "fields": {},
                "floors_added": [],
                "floors_removed": [],
                "floor_changes": [],
                "slot_changes": [],
                "floor_subtitle_changes": [],
                "description": None,
            },
            {
                "kind": "modified",
                "id": "2099-01-02",
                "date_iso": "2099-01-02",
                "date_label": "Sa.02.01.99",
                "title": None,
                "url": "https://www.openground.club/en/schedule/2099-01-02",
                "fields": {"time": {"old": "20:00", "new": "22:00"}},
                "floors_added": [],
                "floors_removed": [],
                "floor_changes": [
                    {
                        "floor": "FREIFELD",
                        "artists_added": ["Test Artist"],
                        "artists_removed": [],
                    }
                ],
                "slot_changes": [
                    {
                        "floor": "FREIFELD",
                        "name": "Existing Artist",
                        "time_old": "21:00",
                        "time_new": "23:00",
                        "bio_changed": True,
                    }
                ],
                "floor_subtitle_changes": [],
                "description": None,
            },
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request that would be sent and exit.",
    )
    parser.add_argument(
        "--message",
        help="Override the message body with this plain text instead of using "
        "the synthetic change set.",
    )
    args = parser.parse_args(argv)

    site_url = os.environ.get("SITE_URL") or None
    run = _fake_run()
    run_at = str(run["run_at"])

    if args.message:
        prefix = "[matrix-notify-test] "
        text_body = prefix + args.message
        from html import escape as _esc
        html_body = f"<strong>{_esc(prefix)}</strong>{_esc(args.message)}"
    else:
        text_body, html_body = format_changes(
            run["changes"],  # type: ignore[arg-type]
            run_at=run_at,
            site_url=site_url,
        )
        text_body = "[matrix-notify-test] " + text_body
        html_body = "<strong>[matrix-notify-test]</strong> " + html_body

    payload = {
        "msgtype": "m.text",
        "body": text_body,
        "format": "org.matrix.custom.html",
        "formatted_body": html_body,
    }
    # Unique txn id so the same test can be re-sent multiple times.
    txn_id = f"openground-test-{uuid.uuid4()}"

    if args.dry_run:
        print(
            json.dumps(
                {"run_at": run_at, "txn_id": txn_id, "payload": payload},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    homeserver = os.environ.get("MATRIX_HOMESERVER")
    access_token = os.environ.get("MATRIX_ACCESS_TOKEN")
    room_id = os.environ.get("MATRIX_ROOM_ID")
    missing = [
        name
        for name, val in (
            ("MATRIX_HOMESERVER", homeserver),
            ("MATRIX_ACCESS_TOKEN", access_token),
            ("MATRIX_ROOM_ID", room_id),
        )
        if not val
    ]
    if missing:
        print(
            "error: missing required env var(s): " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    url = (
        f"{homeserver.rstrip('/')}/_matrix/client/v3/rooms/"
        f"{urllib.parse.quote(room_id)}/send/m.room.message/"  # type: ignore[arg-type]
        f"{urllib.parse.quote(txn_id)}"
    )
    try:
        resp = requests.put(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    except requests.RequestException as err:
        print(f"error: matrix request failed: {err}", file=sys.stderr)
        return 1

    if resp.status_code >= 400:
        print(
            f"error: matrix returned {resp.status_code}: {resp.text[:500]}",
            file=sys.stderr,
        )
        return 1

    try:
        event_id = resp.json().get("event_id", "<unknown>")
    except ValueError:
        event_id = "<unparseable>"
    print(f"ok: posted test message, event_id={event_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
