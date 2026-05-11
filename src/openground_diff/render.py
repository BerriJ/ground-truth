"""Render the static diff site from `data/history.jsonl`."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any, Iterable

UPSTREAM_BASE = "https://www.openground.club/en/schedule/"

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
.nav { margin-bottom: 1.5rem; font-size: 0.95rem; }
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
.text-diff { margin: 0.4rem 0; padding: 0.4rem 0.6rem; background: rgba(127,127,127,0.08);
             border-radius: 0.25rem; white-space: pre-wrap; font-size: 0.9rem; }
.text-diff .label { font-weight: bold; font-size: 0.75rem; text-transform: uppercase;
                    letter-spacing: 0.05em; color: #888; display: block; margin-bottom: 0.2rem; }
.text-diff.old { border-left: 3px solid #cf222e; }
.text-diff.new { border-left: 3px solid #1a7f37; }

/* Per-event page */
.event-meta { color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }
.event-floor { border: 1px solid rgba(127,127,127,0.25); border-radius: 0.4rem;
               padding: 0.75rem 1rem; margin: 1rem 0; }
.event-floor h3 { margin: 0 0 0.5rem; font-size: 1.05rem; }
.event-floor .floor-sub { color: #888; font-size: 0.85rem; font-weight: normal; }
.slot { padding: 0.4rem 0; border-top: 1px dashed rgba(127,127,127,0.25); }
.slot:first-of-type { border-top: 0; }
.slot-details { padding: 0; margin: 0; }
.slot-details > summary { list-style: none; cursor: pointer;
                          display: grid;
                          grid-template-columns: 1.2em 4em 1fr auto;
                          gap: 0.6rem; align-items: baseline; }
.slot-details > summary::-webkit-details-marker { display: none; }
.slot-details:not([open]) > summary .slot-toggle::before { content: "▸"; color: #888; }
.slot-details[open] > summary .slot-toggle::before { content: "▾"; color: #888; }
.slot-details > summary.no-bio { cursor: default; }
.slot-details > summary.no-bio .slot-toggle { visibility: hidden; }
.slot-toggle { font-size: 0.85rem; }
.slot-time { font-variant-numeric: tabular-nums; color: #555; }
.slot-name { font-weight: 600; }
.slot-city { color: #888; font-size: 0.85rem; text-align: right; }
.slot-bio { margin: 0.4rem 0 0.2rem calc(1.2em + 4em + 1.2rem);
            font-size: 0.92rem; color: #888; white-space: pre-wrap; }
.event-description { margin: 1.5rem 0; padding: 0.75rem 1rem;
                     background: rgba(127,127,127,0.06); border-radius: 0.4rem;
                     white-space: pre-wrap; }
.event-description h2 { margin: 0 0 0.5rem; font-size: 1rem; }
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


def _read_current(current_path: Path | None) -> dict[str, dict[str, Any]]:
    if current_path is None or not current_path.exists():
        return {}
    with current_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return {ev["id"]: ev for ev in data.get("events", [])}


def render_site(
    history_path: Path,
    out_dir: Path,
    last_scrape: str | None = None,
    current_path: Path | None = None,
) -> None:
    runs = _read_runs(history_path)
    current_by_id = _read_current(current_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (out_dir / "index.html").write_text(
        _render_index(runs, last_scrape), encoding="utf-8"
    )

    # Collect every slug ever referenced in history and currently scheduled.
    slugs: set[str] = set(current_by_id.keys())
    for run in runs:
        for ch in run.get("changes") or []:
            if ch.get("id"):
                slugs.add(ch["id"])

    event_dir = out_dir / "event"
    if slugs:
        event_dir.mkdir(parents=True, exist_ok=True)
    for slug in sorted(slugs):
        page = _render_event_page(slug, current_by_id.get(slug), runs, last_scrape)
        (event_dir / f"{slug}.html").write_text(page, encoding="utf-8")


def _render_index(runs: list[dict[str, Any]], last_scrape: str | None = None) -> str:
    if last_scrape:
        last_run = last_scrape
    elif runs:
        last_run = runs[0]["run_at"]
    else:
        last_run = "never"
    body_parts: list[str] = []
    body_parts.append("<h1>Open Ground — line-up changes</h1>")
    body_parts.append(
        f'<p class="meta">Last scrape: <time>{escape(last_run)}</time> · '
        f"{len(runs)} run(s) recorded · "
        f'source: <a href="https://www.openground.club/en/">openground.club</a></p>'
    )
    if not runs:
        body_parts.append('<p class="empty">No scrapes yet.</p>')
    for run in runs:
        body_parts.append(_render_run(run))
    return _page("Open Ground — line-up changes", "\n".join(body_parts), css_href="style.css")


def _render_run(run: dict[str, Any]) -> str:
    run_at = run.get("run_at", "")
    changes = run.get("changes") or []
    parts = [f'<section class="run"><h2>{escape(run_at)}</h2>']
    if not changes:
        parts.append('<p class="empty">No changes.</p>')
    else:
        for change in changes:
            parts.append(_render_change(change, css_prefix=""))
    parts.append("</section>")
    return "\n".join(parts)


def _render_change(change: dict[str, Any], css_prefix: str = "") -> str:
    kind = change.get("kind", "modified")
    title = change.get("title")
    date_label = change.get("date_label") or change.get("date_iso") or ""
    headline_text = title or date_label or change.get("id") or ""
    slug = change.get("id")
    link_target = f"{css_prefix}event/{slug}.html" if slug else None
    headline_inner = escape(headline_text)
    if link_target:
        headline_inner = f'<a href="{escape(link_target)}">{headline_inner}</a>'
    parts = [f'<div class="change {escape(kind)}">']
    suffix = (
        f" <small>· {escape(date_label)}</small>"
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
    for fsc in change.get("floor_subtitle_changes") or []:
        floor = fsc.get("floor", "")
        old = fsc.get("old") or "—"
        new = fsc.get("new") or "—"
        items.append(
            f"<li><strong>{escape(floor)}</strong> subtitle: "
            f"{escape(old)} → {escape(new)}</li>"
        )
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
    # Suppress slot-level changes (time, bio) for artists that are already
    # reported as added or removed on the same floor.
    moved: set[tuple[str, str]] = set()
    for fc in change.get("floor_changes") or []:
        floor = fc.get("floor", "")
        for a in (fc.get("artists_added") or []) + (fc.get("artists_removed") or []):
            moved.add((floor, a))
    for sc in change.get("slot_changes") or []:
        floor = sc.get("floor", "")
        name = sc.get("name", "")
        if (floor, name) in moved:
            continue
        parts: list[str] = []
        t_old = sc.get("time_old")
        t_new = sc.get("time_new")
        if t_old or t_new:
            parts.append(
                f"time {escape(str(t_old or '—'))} → {escape(str(t_new or '—'))}"
            )
        if sc.get("bio_changed"):
            parts.append("bio updated")
        if parts:
            items.append(
                f"<li><strong>{escape(floor)}</strong> · {escape(name)}: "
                + "; ".join(parts)
                + "</li>"
            )
    desc = change.get("description") or None
    if desc:
        old = desc.get("old") or ""
        new = desc.get("new") or ""
        if old:
            items.append(
                '<li>Description (old):'
                f'<div class="text-diff old"><span class="label">old</span>'
                f"{escape(old)}</div></li>"
            )
        if new:
            items.append(
                '<li>Description (new):'
                f'<div class="text-diff new"><span class="label">new</span>'
                f"{escape(new)}</div></li>"
            )
    if not items:
        return []
    return ["<ul>", *items, "</ul>"]


def _render_event_page(
    slug: str,
    current: dict[str, Any] | None,
    runs: list[dict[str, Any]],
    last_scrape: str | None,
) -> str:
    # Filter runs to those that mention this slug.
    relevant: list[tuple[str, dict[str, Any]]] = []
    for run in runs:
        for ch in run.get("changes") or []:
            if ch.get("id") == slug:
                relevant.append((run.get("run_at", ""), ch))

    # Header
    if current is not None:
        date_label = current.get("date_label") or current.get("date_iso") or slug
        title = current.get("title")
        category = current.get("category")
        time_str = current.get("time")
    else:
        # Fall back to most recent run entry for this slug
        last_ch = relevant[0][1] if relevant else {}
        date_label = last_ch.get("date_label") or last_ch.get("date_iso") or slug
        title = last_ch.get("title")
        category = None
        time_str = None

    headline = title or date_label
    meta_bits: list[str] = []
    if category:
        meta_bits.append(escape(category))
    if date_label and date_label != headline:
        meta_bits.append(escape(date_label))
    if time_str:
        meta_bits.append(escape(time_str))
    meta_bits.append(
        f'<a href="{UPSTREAM_BASE}{escape(slug)}">View on openground.club ↗</a>'
    )

    body: list[str] = []
    body.append('<p class="nav"><a href="../index.html">← All changes</a></p>')
    body.append(f"<h1>{escape(headline)}</h1>")
    body.append(f'<p class="event-meta">{" · ".join(meta_bits)}</p>')

    if current is None:
        body.append(
            '<p class="empty">This event is no longer on the schedule. '
            "Showing change history only.</p>"
        )
    else:
        body.append(_render_event_current(current))

    body.append("<h2>Change history</h2>")
    if not relevant:
        body.append('<p class="empty">No tracked changes for this event.</p>')
    else:
        for run_at, ch in relevant:
            body.append(
                f'<section class="run"><h2>{escape(run_at)}</h2>'
                + _render_change(ch, css_prefix="../")
                + "</section>"
            )

    page_title = f"{headline} — Open Ground line-up changes"
    return _page(page_title, "\n".join(body), css_href="../style.css")


def _render_event_current(ev: dict[str, Any]) -> str:
    parts: list[str] = []
    detail = ev.get("detail")
    floors = (detail or {}).get("floors") or []
    if not floors:
        # Fall back to homepage-style floors (no times/bios)
        for f in ev.get("floors") or []:
            parts.append(_render_simple_floor(f))
    else:
        for f in floors:
            parts.append(_render_detail_floor(f))

    desc = (detail or {}).get("description")
    if desc:
        parts.append(
            '<div class="event-description"><h2>About the night</h2>'
            f"<div>{escape(desc)}</div></div>"
        )
    return "\n".join(parts)


def _render_detail_floor(floor: dict[str, Any]) -> str:
    name = floor.get("name", "")
    subtitle = floor.get("subtitle")
    head = f"<h3>{escape(name)}"
    if subtitle:
        head += f' <span class="floor-sub">— {escape(subtitle)}</span>'
    head += "</h3>"
    slots_html: list[str] = []
    for s in floor.get("slots") or []:
        slots_html.append(_render_slot(s))
    if not slots_html:
        slots_html.append('<p class="empty">No slots announced.</p>')
    return f'<section class="event-floor">{head}{"".join(slots_html)}</section>'


def _render_simple_floor(floor: dict[str, Any]) -> str:
    name = floor.get("name", "")
    artists = floor.get("artists") or []
    items = "".join(f"<li>{escape(a)}</li>" for a in artists)
    return (
        f'<section class="event-floor"><h3>{escape(name)}</h3>'
        f'<ul class="floor-artists">{items}</ul></section>'
    )


def _render_slot(slot: dict[str, Any]) -> str:
    time_s = slot.get("time") or ""
    name = slot.get("name") or ""
    city = slot.get("city")
    bio = slot.get("bio")
    summary_cls = "" if bio else " class=\"no-bio\""
    summary = (
        f"<summary{summary_cls}>"
        '<span class="slot-toggle"></span>'
        f'<span class="slot-time">{escape(time_s)}</span>'
        f'<span class="slot-name">{escape(name)}</span>'
        f'<span class="slot-city">{escape(city or "")}</span>'
    )
    summary += "</summary>"
    bio_html = f'<div class="slot-bio">{escape(bio)}</div>' if bio else ""
    return f'<div class="slot"><details class="slot-details">{summary}{bio_html}</details></div>'


def _page(title: str, body: str, css_href: str = "style.css") -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f'<link rel="stylesheet" href="{escape(css_href)}">\n'
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )
