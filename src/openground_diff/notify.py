"""Format diff changes as plain text + HTML for Matrix notifications."""
from __future__ import annotations

from html import escape
from typing import Any

# Colored Unicode squares used as per-kind markers. These are plain text
# characters (rendered by the system emoji font), so they appear correctly
# on every Matrix client regardless of HTML/CSS support — unlike <font
# color> or <span style="color"> which Element on Android/iOS strips.
_KIND_MARKER = {
    "added": "🟩",      # green
    "cancelled": "🟥",  # red
    "modified": "🟧",   # orange
}


def _kind_marker(kind: str) -> str:
    return _KIND_MARKER.get(kind, "▪")


def _headline(change: dict[str, Any]) -> str:
    """Single label for an event, matching the web page (title OR date)."""
    title = change.get("title")
    if title:
        return title
    return (
        change.get("date_label")
        or change.get("date_iso")
        or change.get("id")
        or ""
    )


def format_changes(
    changes: list[dict[str, Any]],
    run_at: str,
    site_url: str | None = None,
) -> tuple[str, str]:
    """Return ``(plain_text, html)`` bodies for a Matrix ``m.text`` message.

    ``changes`` follows the schema serialized by ``Change.to_dict()``.
    ``site_url`` is the base URL of the deployed site; when set, event
    headlines link to the per-event page on our site rather than to
    openground.club. ``run_at`` is accepted for backwards compatibility but
    no longer rendered — the Matrix client already shows the sender and the
    receive timestamp.
    """
    del run_at  # intentionally unused

    text_lines: list[str] = []
    html_blocks: list[str] = []
    for change in changes:
        url = _event_url(change, site_url)
        text_lines.extend(_change_text(change, url))
        html_blocks.append(_change_html(change, url))

    return "\n".join(text_lines), "\n".join(html_blocks)


def _event_url(change: dict[str, Any], site_url: str | None) -> str | None:
    """Pick the best link target for an event.

    Prefer our own per-event page on the deployed site (when ``site_url`` is
    set and the change has an id); fall back to the upstream openground.club
    URL otherwise.
    """
    slug = change.get("id")
    if site_url and slug:
        return f"{site_url.rstrip('/')}/event/{slug}.html"
    return change.get("url")


def _change_text(change: dict[str, Any], url: str | None) -> list[str]:
    kind = change.get("kind", "modified")
    headline = _headline(change)
    head = f"- {_kind_marker(kind)} {headline}"
    if url:
        head += f" ({url})"
    lines = [head]
    for sub in _change_sub_lines(change):
        lines.append(f"  - {sub}")
    return lines


def _change_html(change: dict[str, Any], url: str | None) -> str:
    kind = change.get("kind", "modified")
    headline = _headline(change)
    headline_html = escape(headline)
    if url:
        headline_html = f'<a href="{escape(url, quote=True)}">{headline_html}</a>'
    # Top-level event line is a plain block (colored emoji marker + headline);
    # sub-changes for the event are listed as a nested <ul>.
    # Using <div> rather than <p> avoids the large vertical margins many
    # Matrix clients (e.g. Element) apply to paragraphs.
    head = f"<div>{_kind_marker(kind)} {headline_html}</div>"
    subs = list(_change_sub_lines(change))
    if not subs:
        return head
    items = "".join(f"<li>{escape(sub)}</li>" for sub in subs)
    return f"{head}<ul>{items}</ul>"


def _change_sub_lines(change: dict[str, Any]) -> list[str]:
    if change.get("kind") in ("added", "cancelled"):
        return []
    out: list[str] = []
    fields = change.get("fields") or {}
    for key, val in fields.items():
        out.append(f"{key}: {val.get('old')} → {val.get('new')}")
    for name in change.get("floors_added") or []:
        out.append(f"Floor added: {name}")
    for name in change.get("floors_removed") or []:
        out.append(f"Floor removed: {name}")
    # Track (floor, artist) pairs that are reported as line-up adds/removes,
    # so we don't *also* report a slot change for the same artist (e.g. a
    # "bio updated" entry that is really just the artist appearing for the
    # first time).
    moved: set[tuple[str, str]] = set()
    for fc in change.get("floor_changes") or []:
        floor = fc.get("floor", "")
        for a in fc.get("artists_added") or []:
            out.append(f"{floor}: + {a}")
            moved.add((floor, a))
        for a in fc.get("artists_removed") or []:
            out.append(f"{floor}: − {a}")
            moved.add((floor, a))
    for fsc in change.get("floor_subtitle_changes") or []:
        floor = fsc.get("floor", "")
        old = fsc.get("old") or "—"
        new = fsc.get("new") or "—"
        out.append(f"{floor} subtitle: {old} → {new}")
    for sc in change.get("slot_changes") or []:
        floor = sc.get("floor", "")
        name = sc.get("name", "")
        if (floor, name) in moved:
            continue
        bits: list[str] = []
        t_old = sc.get("time_old")
        t_new = sc.get("time_new")
        if t_old or t_new:
            bits.append(f"time {t_old or '—'} → {t_new or '—'}")
        if sc.get("bio_changed"):
            bits.append("bio updated")
        if bits:
            out.append(f"{floor} · {name}: " + "; ".join(bits))
    if change.get("description"):
        out.append("description updated")
    return out
