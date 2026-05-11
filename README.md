# Ground-Truth

Scrapes the [Open Ground](https://www.openground.club/en/) homepage on a
schedule and publishes a static page that lists meaningful changes between
scrapes (new events, cancellations of future events, line-up edits, ticket
state flips, time changes). It additionally fetches each event's detail page
(`/en/schedule/<date>`) and tracks set times, artist bios, floor subtitles
and the night's general description, surfacing those as deeper diffs on
per-event sub-pages. Past events that simply roll off the homepage are
not reported.

## Local usage

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Run against the live site (writes data/ and site/):
python -m openground_diff.main

# Or against a local HTML snapshot:
python -m openground_diff.main --from-file "Open Ground.html"

pytest
```

Open `site/index.html` in your browser.

## Layout

- `src/openground_diff/scrape.py` — fetch + HTML parser.
- `src/openground_diff/diff.py` — snapshot diff engine.
- `src/openground_diff/render.py` — static site renderer.
- `src/openground_diff/main.py` — CLI orchestrator.
- `data/current.json` — latest snapshot.
- `data/history.jsonl` — append-only log of change runs (the source of the rendered site).
- `site/` — generated static site (deployed to GitHub Pages).

## Automation

`.github/workflows/scrape.yml` runs the CLI on a 6-hour cron, commits any
changes under `data/` and `site/`, and deploys `site/` to GitHub Pages.
Enable Pages once in the repo settings (source: GitHub Actions).

### Matrix notifications (optional)

After a successful commit the workflow runs `scripts/notify_matrix.py`,
which posts the latest run's changes to a Matrix room via the Client-Server
API. The step no-ops (and never fails the job) when secrets are absent,
so forks work out of the box.

Configure these repository secrets to enable it:

- `MATRIX_HOMESERVER` — e.g. `https://matrix.example.org`
- `MATRIX_ACCESS_TOKEN` — bot user's access token (the bot must already be
  joined to the target room, and the room must not be E2EE)
- `MATRIX_ROOM_ID` — internal room id, e.g. `!abcdef:example.org`

Optional repository variable:

- `SITE_URL` — public URL of the deployed site, linked from the message header.

Idempotency is provided by `data/.last_notified` (gitignored, cached
between runs by `actions/cache`).

#### Testing

If you have set up the above environment variables locally, you can test the notification service as follows:

```sh
# Inspect the request without sending:
python scripts/test_matrix_notify.py --dry-run

# Send a synthetic change set to the configured room:
python scripts/test_matrix_notify.py

# Send a custom one-liner instead:
python scripts/test_matrix_notify.py --message "hello from ground-truth"
```