# openground-diff

Scrapes the [Open Ground](https://www.openground.club/de/) homepage on a
schedule and publishes a static page that lists meaningful changes between
scrapes (new events, cancellations of future events, line-up edits, ticket
state flips, time changes). Past events that simply roll off the homepage are
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
