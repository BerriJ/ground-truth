"""Format diff changes as plain text + HTML for Matrix notifications."""
from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import urljoin

SITE_BASE_URL = "https://www.openground.club"

_KIND_LABEL = {
    "added": "Added",
    "cancelled": "Cancelled",
    "modified": "Modified",
}


def format_changes(
    changes: list[dict[str, Any]],
    run_at: str,
    site_url: str | None = None,
) -> tuple[str, str]:
    """Return ``(plain_text, html)`` bodies for a Matrix ``m.text`` message.

    ``changes`` follows the schema serialized by ``Change.to_dict()``.
    ``site_url`` is the public URL of the rendered site; when present it is
    linked in the header.
    """
    n = len(changes)
    header_text = f"Open Ground — {n} change(s) · {run_at}"
    if site_url:
        header_html = (
            f'<strong>Open Ground</strong> — {n} change(s) · '
            f'<a href="{escape(site_url, quote=True)}">{escape(run_at)}</a>'
        )
    else:
        header_html = f"<strong>Open Ground</strong> — {n} change(s) · {escape(run_at)}"

    text_lines: list[str] = [header_text]
    html_items: list[str] = []
    for change in changes:
        text_lines.extend(_change_text(change))
        html_items.append(_change_html(change))

    html = header_html
    if html_items:
        html += "\n<ul>\n" + "\n".join(html_items) + "\n</ul>"
    return "\n".join(text_lines), html


def _change_text(change: dict[str, Any]) -> list[str]:
    kind = change.get("kind", "modified")
    title = change.get("title") or change.get("id") or ""
    date_label = change.get("date_label") or change.get("date_iso") or ""
    url = change.get("url")
    head = f"- [{_KIND_LABEL.get(kind, kind)}] {title} · {date_label}"
    if url:
        head += f" ({urljoin(SITE_BASE_URL, url)})"
    lines = [head]
    for sub in _change_sub_lines(change):
        lines.append(f"  - {sub}")
    return lines


def _change_html(change: dict[str, Any]) -> str:
    kind = change.get("kind", "modified")
    title = change.get("title") or change.get("id") or ""
    date_label = change.get("date_label") or change.get("date_iso") or ""
    url = change.get("url")
    title_html = escape(title)
    if url:
        href = urljoin(SITE_BASE_URL, url)
        title_html = f'<a href="{escape(href, quote=True)}">{title_html}</a>'
    parts = [
        f"<li><strong>[{escape(_KIND_LABEL.get(kind, kind))}]</strong> "
        f"{title_html} · {escape(date_label)}"
    ]
    subs = list(_change_sub_lines(change))
    if subs:
        parts.append("<ul>")
        for sub in subs:
            parts.append(f"<li>{escape(sub)}</li>")
        parts.append("</ul>")
    parts.append("</li>")
    return "".join(parts)


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
    for fc in change.get("floor_changes") or []:
        floor = fc.get("floor", "")
        for a in fc.get("artists_added") or []:
            out.append(f"{floor}: + {a}")
        for a in fc.get("artists_removed") or []:
            out.append(f"{floor}: − {a}")
    return out
