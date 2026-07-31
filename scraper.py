import logging
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from config import Config
from database import Database

logger = logging.getLogger(__name__)


async def fetch_calendar(config: Optional[Config] = None, db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """
    Scrapes ForexFactory High Impact economic calendar events using Playwright async API.
    Caches events into SQLite database.
    """
    cfg = config or Config()
    database = db or Database(cfg.DB_PATH, cfg)

    logger.info("Starting Playwright to scrape ForexFactory calendar...")
    events: List[Dict[str, Any]] = []

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright module not installed.")
        return database.get_news_events()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                timezone_id="UTC",
            )
            page = await context.new_page()

            logger.info(f"Navigating to {cfg.CALENDAR_URL}")
            await page.goto(cfg.CALENDAR_URL, wait_until="domcontentloaded", timeout=cfg.SCRAPE_TIMEOUT_MS)

            try:
                await page.wait_for_selector("table.calendar__table", timeout=15000)
            except Exception as e:
                logger.warning(f"Timeout waiting for calendar table: {e}")

            content = await page.content()
            await browser.close()

            events = parse_forexfactory_html(content, cfg)
            if events and database:
                database.save_news_events(events)
                logger.info(f"Successfully scraped and cached {len(events)} High Impact news events.")
            return events

    except Exception as err:
        logger.exception(f"Error scraping ForexFactory with Playwright: {err}")
        if database:
            cached = database.get_news_events()
            if cached:
                logger.info(f"Returning {len(cached)} cached news events from database fallback.")
                return cached
        return []


def parse_forexfactory_html(html_content: str, config: Config) -> List[Dict[str, Any]]:
    """
    Parses HTML content from ForexFactory calendar for High Impact events matching watched currencies.
    """
    soup = BeautifulSoup(html_content, "lxml")
    rows = soup.select("tr.calendar__row")
    events: List[Dict[str, Any]] = []

    current_date_str = ""
    now_utc = datetime.now(timezone.utc)

    for row in rows:
        date_cell = row.select_one("td.calendar__date")
        if date_cell and date_cell.text.strip():
            current_date_str = date_cell.text.strip()

        impact_cell = row.select_one("td.calendar__impact span")
        if not impact_cell:
            continue

        impact_class = impact_cell.get("class", [])
        impact_title = impact_cell.get("title", "").lower()
        is_high_impact = "calendar__impact-icon--high" in impact_class or "red" in impact_title or "high" in impact_title
        if not is_high_impact:
            continue

        currency_cell = row.select_one("td.calendar__currency")
        currency = currency_cell.text.strip().upper() if currency_cell else ""
        if currency not in config.WATCHED_CURRENCIES:
            continue

        title_cell = row.select_one("td.calendar__event")
        title = title_cell.text.strip() if title_cell else ""
        if not title:
            continue

        time_cell = row.select_one("td.calendar__time")
        time_str = time_cell.text.strip() if time_cell else ""

        forecast_cell = row.select_one("td.calendar__forecast")
        forecast = forecast_cell.text.strip() if forecast_cell else "-"
        previous_cell = row.select_one("td.calendar__previous")
        previous = previous_cell.text.strip() if previous_cell else "-"

        timestamp_utc = parse_event_timestamp(current_date_str, time_str, now_utc)
        event_id = f"{currency}_{title}_{timestamp_utc}".replace(" ", "_")

        events.append({
            "event_id": event_id,
            "title": title,
            "currency": currency,
            "impact": "high",
            "timestamp_utc": timestamp_utc,
            "event_timestamp": timestamp_utc,
            "forecast": forecast or "-",
            "previous": previous or "-",
            "time_str": time_str,
            "date_str": current_date_str,
        })

    return events


def parse_event_timestamp(date_str: str, time_str: str, now_utc: datetime) -> int:
    """
    Parses day/time text from ForexFactory into UTC epoch timestamp.
    """
    try:
        year = now_utc.year
        clean_date = f"{date_str} {year}".strip()

        if "All Day" in time_str or "Day" in time_str or not time_str:
            dt = datetime.strptime(clean_date, "%a %b %d %Y").replace(tzinfo=timezone.utc)
            return int(dt.timestamp())

        dt_str = f"{clean_date} {time_str}".strip()
        dt = datetime.strptime(dt_str, "%a %b %d %Y %I:%M%p").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return int(now_utc.timestamp())
