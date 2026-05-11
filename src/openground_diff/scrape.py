"""Scrape and parse the Open Ground homepage and event-day pages."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

SITE_BASE = "https://www.openground.club"
HOMEPAGE_URL = f"{SITE_BASE}/en/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SCHEDULE_RE = re.compile(r"/(?:de|en)/schedule/(?P<slug>[^/?#]+)")
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
class Slot:
    """A single artist slot on the event detail page."""

    name: str
    time: str | None = None
    city: str | None = None
    bio: str | None = None


@dataclass
class DetailedFloor:
    name: str
    subtitle: str | None = None
    slots: list[Slot] = field(default_factory=list)


@dataclass
class EventDetail:
    floors: list[DetailedFloor] = field(default_factory=list)
    description: str | None = None


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
    detail: EventDetail | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def event_page_url(slug: str) -> str:
    return f"{SITE_BASE}/en/schedule/{slug}"


def fetch(url: str = HOMEPAGE_URL, timeout: float = 60.0) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en,de;q=0.7",
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
        url=event_page_url(slug),
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


def fetch_event(slug: str, timeout: float = 60.0) -> str:
    return fetch(event_page_url(slug), timeout=timeout)


def parse_event_detail(html: str) -> EventDetail:
    """Parse an event-day page into a structured ``EventDetail``."""
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one(".main-layer__content--event") or soup
    floors: list[DetailedFloor] = []
    for section in main.select(".event-info.event-info--new"):
        floor = _parse_detail_floor(section)
        if floor is not None:
            floors.append(floor)

    description: str | None = None
    desc_block = main.select_one(".article-box--text .block--text.format-text")
    if desc_block is not None:
        description = _block_text(desc_block) or None

    return EventDetail(floors=floors, description=description)


def _parse_detail_floor(section: Tag) -> DetailedFloor | None:
    label = section.select_one(".event-info__floor__label")
    if label is None:
        return None
    name = _text(label) or ""
    if not name:
        return None
    sub_el = section.select_one(".event-info__floor__value")
    subtitle = _text(sub_el) if sub_el is not None else None

    slots: list[Slot] = []
    for item in section.select(".event-info__item"):
        slot = _parse_slot(item)
        if slot is not None:
            slots.append(slot)
    return DetailedFloor(name=name, subtitle=subtitle, slots=slots)


def _parse_slot(item: Tag) -> Slot | None:
    name_el = item.select_one(".event-item__accordion-top-name")
    if name_el is None:
        return None
    name = _clean_artist(name_el)
    if not name:
        return None
    time_el = item.select_one(".event-item__accordion-top-time")
    slot_time = _text(time_el) if time_el is not None else None
    city_el = item.select_one(".event-item__accordion-top-city")
    city = _text(city_el) if city_el is not None else None
    bio_parts: list[str] = []
    for text_block in item.select(".event-item__accordion-content-text"):
        txt = _block_text(text_block)
        if txt:
            bio_parts.append(txt)
    bio = "\n\n".join(bio_parts) if bio_parts else None
    return Slot(name=name, time=slot_time, city=city, bio=bio)


def _block_text(el: Tag) -> str:
    """Convert a rich-text block (paragraphs + <br>) into clean plain text."""
    paragraphs: list[str] = []
    for p in el.find_all("p"):
        txt = p.get_text("\n", strip=False)
        txt = txt.replace("\xa0", " ")
        txt = re.sub(r"[ \t]+", " ", txt)
        txt = re.sub(r" *\n *", "\n", txt)
        txt = re.sub(r"\n{2,}", "\n", txt).strip()
        if txt:
            paragraphs.append(txt)
    if paragraphs:
        return "\n\n".join(paragraphs)
    txt = el.get_text(" ", strip=True)
    return txt or ""


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
