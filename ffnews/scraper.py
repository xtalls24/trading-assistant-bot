"""
Forex Factory calendar scraper.

Replaces the old JSON-endpoint client (ffnews/news.py) which was rate-limited.
This module uses Playwright to render https://www.forexfactory.com/calendar
in a headless browser and BeautifulSoup/lxml to parse the resulting HTML
table into structured event dicts.

Design goals:
- Never raise out of `fetch_calendar()` — on any failure, log and return [].
- Keep a single Playwright/browser lifecycle per call (no leaked browsers).
- Be resilient to minor markup changes by using multiple fallback selectors
  and defensive parsing for every field.
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config import Config

logger = logging.getLogger(__name__)

_cfg = Config()

# Forex Factory renders impact as a colored icon with one of these classes/titles.
_HIGH_IMPACT_MARKERS = ("high", "red")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_calendar(cfg: Optional[Config] = None) -> List[Dict[str, Any]]:
    """Scrape this week's Forex Factory calendar.

    Returns a list of event dicts with keys:
        id, title, impact, currency, timestamp_utc, forecast, previous, raw
    On any failure (navigation timeout, layout change, blocked page, etc.)
    this logs the reason and returns an empty list. It never raises, so the
    bot (scheduler + command handlers) stays alive even if scraping breaks.
    """
    cfg = cfg or _cfg
    html = await _get_calendar_html(cfg)
    if html is None:
        return []

    try:
        events = _parse_calendar_html(html, cfg)
        logger.info("Scraped %d calendar events", len(events))
        return events
    except Exception:
        logger.exception("Failed to parse Forex Factory calendar HTML")
        return []


async def _get_calendar_html(cfg: Config) -> Optional[str]:
    """Launch a headless browser, navigate to the calendar, and return the
    fully rendered HTML. Returns None on any navigation/loading failure.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(user_agent=_USER_AGENT)
                page = await context.new_page()
                await page.goto(
                    cfg.CALENDAR_URL,
                    wait_until="domcontentloaded",
                    timeout=cfg.SCRAPE_TIMEOUT_MS,
                )

                # Wait for a stable, semantic selector rather than a specific
                # CSS class hash, which Forex Factory changes periodically.
                try:
                    await page.wait_for_selector(
                        "table.calendar__table, table[class*='calendar']",
                        timeout=cfg.SCRAPE_TIMEOUT_MS,
                    )
                except PlaywrightTimeoutError:
                    logger.warning(
                        "Calendar table selector did not appear within timeout; "
                        "page layout may have changed."
                    )
                    return None

                html = await page.content()
                return html
            finally:
                await browser.close()
    except PlaywrightTimeoutError as e:
        logger.error("Timed out loading Forex Factory calendar: %s", e)
        return None
    except Exception as e:
        logger.exception("Unexpected error while scraping Forex Factory: %s", e)
        return None


def _parse_calendar_html(html: str, cfg: Config) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.calendar__table") or soup.select_one(
        "table[class*='calendar']"
    )
    if table is None:
        logger.warning("Calendar table not found in scraped HTML")
        return []

    rows = table.select("tr.calendar__row") or table.select("tr[data-event-id]")
    if not rows:
        logger.warning("No calendar rows found in scraped HTML")
        return []

    tz = ZoneInfo(cfg.TIMEZONE)
    events: List[Dict[str, Any]] = []
    current_date: Optional[datetime.date] = None
    now_year = datetime.now(tz).year

    for row in rows:
        try:
            # Each new day starts a row containing a date cell; subsequent
            # rows for the same day omit it, so we carry the last seen date.
            date_cell = row.select_one(".calendar__date")
            if date_cell and date_cell.get_text(strip=True):
                current_date = _parse_date_cell(date_cell.get_text(strip=True), now_year)

            if current_date is None:
                continue

            currency_cell = row.select_one(".calendar__currency")
            currency = (currency_cell.get_text(strip=True) if currency_cell else "").upper()
            if currency not in cfg.WATCHED_CURRENCIES:
                continue

            impact_cell = row.select_one(".calendar__impact")
            impact = _extract_impact(impact_cell)
            if impact != "high":
                continue

            title_cell = row.select_one(".calendar__event")
            title = title_cell.get_text(strip=True) if title_cell else "Unknown"

            time_cell = row.select_one(".calendar__time")
            time_text = time_cell.get_text(strip=True) if time_cell else ""
            event_dt = _combine_date_time(current_date, time_text, tz)
            if event_dt is None:
                # All Day / Tentative events with no fixed time are skipped
                # for notification purposes but could be surfaced later.
                continue

            forecast_cell = row.select_one(".calendar__forecast")
            previous_cell = row.select_one(".calendar__previous")

            event_id = row.get("data-event-id") or f"{currency}-{title}-{event_dt.isoformat()}"

            events.append(
                {
                    "id": str(event_id),
                    "title": title,
                    "impact": "high",
                    "currency": currency,
                    "timestamp_utc": int(event_dt.astimezone(timezone.utc).timestamp()),
                    "forecast": forecast_cell.get_text(strip=True) if forecast_cell else "",
                    "previous": previous_cell.get_text(strip=True) if previous_cell else "",
                    "raw": {},
                }
            )
        except Exception:
            # A single malformed row should never abort the whole scrape.
            logger.exception("Failed to parse a calendar row; skipping it")
            continue

    return events


def _extract_impact(impact_cell) -> str:
    if impact_cell is None:
        return ""
    # Impact is usually conveyed via a <span> title attribute or icon class,
    # e.g. <span class="icon icon--ff-impact-red" title="High Impact Expected">
    span = impact_cell.select_one("span")
    title_attr = (span.get("title") if span else "") or ""
    class_attr = " ".join(span.get("class", []) if span else [])
    combined = f"{title_attr} {class_attr}".lower()
    if any(marker in combined for marker in _HIGH_IMPACT_MARKERS):
        return "high"
    return "other"


def _parse_date_cell(text: str, year: int):
    # Forex Factory date cells look like "Mon Jul 28" or "JulÂ 28".
    cleaned = text.replace("\xa0", " ").strip()
    for fmt in ("%a %b %d", "%b %d"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.replace(year=year).date()
        except ValueError:
            continue
    logger.debug("Could not parse calendar date cell: %r", text)
    return None


def _combine_date_time(date_obj, time_text: str, tz: ZoneInfo):
    time_text = time_text.strip().lower()
    if not time_text or time_text in ("all day", "tentative", "-"):
        return None
    for fmt in ("%I:%M%p", "%I%p"):
        try:
            t = datetime.strptime(time_text, fmt)
            return datetime(
                date_obj.year, date_obj.month, date_obj.day, t.hour, t.minute, tzinfo=tz
            )
        except ValueError:
            continue
    logger.debug("Could not parse calendar time cell: %r", time_text)
    return None
