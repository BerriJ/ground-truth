"""Post the latest history.jsonl run to a Matrix room.

Reads the last line of ``data/history.jsonl`` and PUTs an
``m.room.message`` to the configured room via the Matrix Client-Server
API. Designed to be invoked from the GitHub Actions workflow after a
successful commit. Exits 0 silently when required env vars are missing,
when there are no changes, or when the run was already notified, so
forks without secrets do not break the job.

Required env vars:
    MATRIX_HOMESERVER       e.g. https://matrix.example.org
    MATRIX_ACCESS_TOKEN     bot user access token
    MATRIX_ROOM_ID          e.g. !abcdef:example.org

Optional env vars:
    SITE_URL                public URL of the rendered site
    HISTORY_PATH            path to history.jsonl (default data/history.jsonl)
    LAST_NOTIFIED_PATH      idempotency marker (default data/.last_notified)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import requests

from openground_diff.notify import format_changes


def _read_last_run(history_path: Path) -> dict[str, Any] | None:
    if not history_path.exists():
        return None
    last: str | None = None
    with history_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                last = line
    if last is None:
        return None
    return json.loads(last)


def _build_payload(run: dict[str, Any], site_url: str | None) -> dict[str, Any]:
    body, html = format_changes(
        run.get("changes") or [],
        run_at=run.get("run_at", ""),
        site_url=site_url,
    )
    return {
        "msgtype": "m.text",
        "body": body,
        "format": "org.matrix.custom.html",
        "formatted_body": html,
    }


def _txn_id(run_at: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in run_at)
    return f"openground-{safe}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the request that would be sent and exit.")
    args = parser.parse_args(argv)

    history_path = Path(os.environ.get("HISTORY_PATH", "data/history.jsonl"))
    last_notified_path = Path(
        os.environ.get("LAST_NOTIFIED_PATH", "data/.last_notified")
    )
    site_url = os.environ.get("SITE_URL") or None

    run = _read_last_run(history_path)
    if run is None or not (run.get("changes") or []):
        print("notify: no changes to report", file=sys.stderr)
        return 0

    run_at = run.get("run_at", "")
    if last_notified_path.exists():
        prev = last_notified_path.read_text(encoding="utf-8").strip()
        if prev == run_at:
            print(f"notify: already sent for {run_at}", file=sys.stderr)
            return 0

    payload = _build_payload(run, site_url)

    if args.dry_run:
        print(json.dumps({"run_at": run_at, "txn_id": _txn_id(run_at),
                          "payload": payload}, indent=2, ensure_ascii=False))
        return 0

    homeserver = os.environ.get("MATRIX_HOMESERVER")
    access_token = os.environ.get("MATRIX_ACCESS_TOKEN")
    room_id = os.environ.get("MATRIX_ROOM_ID")
    if not (homeserver and access_token and room_id):
        print("notify: matrix env vars missing, skipping", file=sys.stderr)
        return 0

    url = (
        f"{homeserver.rstrip('/')}/_matrix/client/v3/rooms/"
        f"{urllib.parse.quote(room_id)}/send/m.room.message/"
        f"{urllib.parse.quote(_txn_id(run_at))}"
    )
    try:
        resp = requests.put(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if resp.status_code >= 400:
            print(
                f"notify: matrix returned {resp.status_code}: {resp.text[:200]}",
                file=sys.stderr,
            )
            return 0
    except requests.RequestException as err:
        print(f"notify: matrix request failed: {err}", file=sys.stderr)
        return 0

    last_notified_path.parent.mkdir(parents=True, exist_ok=True)
    last_notified_path.write_text(run_at + "\n", encoding="utf-8")
    print(f"notify: posted {len(run.get('changes') or [])} change(s) for {run_at}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
