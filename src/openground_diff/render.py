"""Render the static diff site from `data/history.jsonl`."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

SITE_BASE_URL = "https://www.openground.club"

STYLE_CSS = """\
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    max-width: 52rem;
    margin: 2rem auto;
    padding: 0 1rem;
    line-height: 1.5;
}
h1 { margin-bottom: 0.25rem; }
.meta { color: #666; font-size: 0.9rem; margin-bottom: 2rem; }
section.run { border-top: 1px solid #ccc; padding-top: 1rem; margin-top: 2rem; }
section.run h2 { font-size: 1.1rem; margin: 0 0 0.5rem; }
.empty { color: #888; font-style: italic; }
.change { padding: 0.6rem 0.8rem; margin: 0.5rem 0; border-left: 4px solid #ccc; background: rgba(127,127,127,0.06); }
.change.added { border-left-color: #1a7f37; }
.change.cancelled { border-left-color: #cf222e; }
.change.modified { border-left-color: #9a6700; }
.change h3 { margin: 0 0 0.25rem; font-size: 1rem; }
.change h3 a { color: inherit; }
.kind { display: inline-block; font-size: 0.75rem; text-transform: uppercase;
        letter-spacing: 0.05em; padding: 0.05rem 0.4rem; border-radius: 0.25rem;
        background: rgba(127,127,127,0.15); margin-right: 0.4rem; vertical-align: middle; }
.change ul { margin: 0.25rem 0 0; padding-left: 1.2rem; }
.change li { margin: 0.1rem 0; }
.added-artist::before { content: "+ "; color: #1a7f37; font-weight: bold; }
.removed-artist::before { content: "− "; color: #cf222e; font-weight: bold; }
"""


def _read_runs(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    runs: list[dict[str, Any]] = []
    with history_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            runs.append(json.loads(line))
    runs.sort(key=lambda r: r.get("run_at", ""), reverse=True)
    return runs


def render_site(history_path: Path, out_dir: Path) -> None:
    runs = _read_runs(history_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (out_dir / "index.html").write_text(_render_index(runs), encoding="utf-8")


def _render_index(runs: list[dict[str, Any]]) -> str:
    last_run = runs[0]["run_at"] if runs else "never"
    body_parts: list[str] = []
    body_parts.append(f"<h1>Open Ground — line-up changes</h1>")
    body_parts.append(
        f'<p class="meta">Last scrape: <time>{escape(last_run)}</time> · '
        f'{len(runs)} run(s) recorded · '
        f'source: <a href="https://www.openground.club/de/">openground.club</a></p>'
    )
    if not runs:
        body_parts.append('<p class="empty">No scrapes yet.</p>')
    for run in runs:
        body_parts.append(_render_run(run))
    return _PAGE.format(body="\n".join(body_parts))


def _render_run(run: dict[str, Any]) -> str:
    run_at = run.get("run_at", "")
    changes = run.get("changes") or []
    parts = [f'<section class="run"><h2>{escape(run_at)}</h2>']
    if not changes:
        parts.append('<p class="empty">No changes.</p>')
    else:
        for change in changes:
            parts.append(_render_change(change))
    parts.append("</section>")
    return "\n".join(parts)


def _render_change(change: dict[str, Any]) -> str:
    kind = change.get("kind", "modified")
    title = change.get("title")
    date_label = change.get("date_label") or change.get("date_iso") or ""
    headline_text = title or date_label or change.get("id") or ""
    url = change.get("url")
    headline_inner = escape(headline_text)
    if url:
        href = urljoin(SITE_BASE_URL, url)
        headline_inner = f'<a href="{escape(href)}">{headline_inner}</a>'
    parts = [f'<div class="change {escape(kind)}">']
    suffix = (
        f' <small>· {escape(date_label)}</small>'
        if title and date_label and date_label != headline_text
        else ""
    )
    parts.append(
        f'<h3><span class="kind">{escape(kind)}</span>{headline_inner}{suffix}</h3>'
    )
    parts.extend(_render_change_body(change))
    parts.append("</div>")
    return "\n".join(parts)


def _render_change_body(change: dict[str, Any]) -> Iterable[str]:
    kind = change.get("kind")
    if kind in ("added", "cancelled"):
        return []
    items: list[str] = []
    fields = change.get("fields") or {}
    for key, val in fields.items():
        old = val.get("old")
        new = val.get("new")
        items.append(
            f"<li><strong>{escape(key)}</strong>: "
            f"{escape(str(old))} → {escape(str(new))}</li>"
        )
    for name in change.get("floors_added") or []:
        items.append(f"<li>Floor added: <strong>{escape(name)}</strong></li>")
    for name in change.get("floors_removed") or []:
        items.append(f"<li>Floor removed: <strong>{escape(name)}</strong></li>")
    for fc in change.get("floor_changes") or []:
        floor = fc.get("floor", "")
        sub: list[str] = []
        for a in fc.get("artists_added") or []:
            sub.append(f'<li class="added-artist">{escape(a)}</li>')
        for a in fc.get("artists_removed") or []:
            sub.append(f'<li class="removed-artist">{escape(a)}</li>')
        items.append(
            f"<li><strong>{escape(floor)}</strong> line-up:<ul>"
            + "".join(sub)
            + "</ul></li>"
        )
    if not items:
        return []
    return ["<ul>", *items, "</ul>"]


_PAGE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Open Ground — line-up changes</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
{body}
</body>
</html>
"""
