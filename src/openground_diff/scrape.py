"""Scrape and parse the Open Ground homepage into a list of events."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

HOMEPAGE_URL = "https://www.openground.club/de/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SCHEDULE_RE = re.compile(r"/de/schedule/(?P<slug>[^/?#]+)")
DATE_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})")


@dataclass
class Floor:
    name: str
    artists: list[str]


@dataclass
class Ticket:
    state: str  # "onsale" | "soldout" | "free" | "none"
    url: str | None = None


@dataclass
class Event:
    id: str  # schedule slug
    url: str
    date_iso: str | None
    date_label: str | None
    time: str | None
    category: str | None
    title: str | None
    floors: list[Floor] = field(default_factory=list)
    ticket: Ticket = field(default_factory=lambda: Ticket(state="none"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fetch(url: str = HOMEPAGE_URL, timeout: float = 60.0) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de,en;q=0.7",
    }
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as err:
            last_err = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}") from last_err


def parse_html(html: str) -> list[Event]:
    soup = BeautifulSoup(html, "lxml")
    events: list[Event] = []
    seen: set[str] = set()
    for block in soup.select("div.newhome-block"):
        ev = _parse_block(block)
        if ev is None or ev.id in seen:
            continue
        seen.add(ev.id)
        events.append(ev)
    events.sort(key=lambda e: (e.date_iso or "", e.id))
    return events


def _parse_block(block: Tag) -> Event | None:
    top = block.select_one("a.newhome-block-box__top")
    if top is None or not top.get("href"):
        return None
    href = top["href"]
    m = SCHEDULE_RE.search(href)
    if not m:
        return None
    slug = m.group("slug")
    date_match = DATE_RE.match(slug)
    date_iso = date_match.group("date") if date_match else None

    category = _text(top.select_one(".newhome-block-box__top__category"))
    date_label = _text(top.select_one(".newhome-block-box__top__date"))
    time = _text(top.select_one(".newhome-block-box__top__time"))
    title = _text(block.select_one(".newhome-block-box__title"))

    floors = _parse_floors(block.select_one(".newhome-block-box__content"))
    ticket = _parse_ticket(block.select_one(".newhome-block-box__button"))

    return Event(
        id=slug,
        url=href,
        date_iso=date_iso,
        date_label=date_label,
        time=time,
        category=category,
        title=title,
        floors=floors,
        ticket=ticket,
    )


def _parse_floors(content: Tag | None) -> list[Floor]:
    if content is None:
        return []
    floors: list[Floor] = []
    current: Floor | None = None
    # Walk descendants in document order, picking up floor labels and their
    # following artists container.
    for el in content.find_all(["div"]):
        classes = el.get("class") or []
        if "newhome-featuredbox__floor__label" in classes:
            name = _text(el) or ""
            current = Floor(name=name, artists=[])
            floors.append(current)
        elif "newhome-featuredbox__artists" in classes and current is not None:
            for set_el in el.select(".home-featuredbox__set"):
                artist = _clean_artist(set_el)
                if artist:
                    current.artists.append(artist)
            current = None  # consumed
    return floors


def _parse_ticket(button_block: Tag | None) -> Ticket:
    if button_block is None:
        return Ticket(state="none")
    a = button_block.select_one("a.link-button--ticket")
    if a is not None and a.get("href"):
        return Ticket(state="onsale", url=a["href"])
    btn = button_block.select_one("button.link-button--ticket")
    if btn is not None:
        classes = btn.get("class") or []
        if "link-button--ticket--soldout" in classes:
            return Ticket(state="soldout")
        if "link-button--ticket--free" in classes:
            return Ticket(state="free")
    return Ticket(state="none")


def _text(el: Tag | None) -> str | None:
    if el is None:
        return None
    txt = el.get_text(" ", strip=True)
    return txt or None


def _clean_artist(el: Tag) -> str:
    # Strip emoji spans, then collapse whitespace.
    clone = BeautifulSoup(str(el), "lxml")
    for emoji in clone.select("span.emoji"):
        emoji.decompose()
    txt = clone.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", txt).strip()
