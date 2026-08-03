import logging
import asyncio
import json
import urllib.request
import ssl
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from config import Config
from database import Database

logger = logging.getLogger(__name__)


async def fetch_calendar(config: Optional[Config] = None, db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """
    Fetches High Impact economic calendar events using TradingView Economic Calendar API.
    Caches events into SQLite database.
    """
    cfg = config or Config()
    database = db or Database(cfg.DB_PATH, cfg)

    logger.info("Fetching economic calendar events from TradingView API...")
    events: List[Dict[str, Any]] = []

    try:
        loop = asyncio.get_running_loop()
        events = await loop.run_in_executor(None, fetch_tradingview_events, cfg)

        if events and database:
            database.save_news_events(events)
            logger.info(f"Successfully fetched and cached {len(events)} High Impact news events.")
            return events
        elif database:
            cached = database.get_news_events()
            if cached:
                logger.info(f"API returned 0 matching events, returning {len(cached)} cached news events.")
                return cached
        return events

    except Exception as err:
        logger.exception(f"Error fetching TradingView economic calendar: {err}")
        if database:
            cached = database.get_news_events()
            if cached:
                logger.info(f"Returning {len(cached)} cached news events from database fallback.")
                return cached
        return []


def fetch_tradingview_events(config: Config) -> List[Dict[str, Any]]:
    """
    Queries TradingView Economic Calendar API for events over a 9-day window (yesterday to +8 days).
    Filters high-impact events (importance=1) for watched currencies.
    """
    now_utc = datetime.now(timezone.utc)
    start_dt = (now_utc - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
    end_dt = (now_utc + timedelta(days=8)).strftime("%Y-%m-%dT23:59:59.000Z")

    url = f"https://economic-calendar.tradingview.com/events?from={start_dt}&to={end_dt}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
        data = json.loads(res.read().decode("utf-8"))

    raw_events = data.get("result", [])
    parsed_events: List[Dict[str, Any]] = []

    watched = set(config.WATCHED_CURRENCIES)

    for item in raw_events:
        # TradingView importance: 1 = High Impact
        importance = item.get("importance")
        if importance != 1:
            continue

        currency = (item.get("currency") or item.get("country") or "").upper()
        if currency not in watched:
            continue

        title = item.get("title", "").strip()
        if not title:
            continue

        date_iso = item.get("date")
        if not date_iso:
            continue

        try:
            clean_date = date_iso.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_date)
            timestamp_utc = int(dt.timestamp())
        except Exception:
            continue

        forecast = str(item.get("forecast") or "-")
        previous = str(item.get("previous") or "-")

        event_id = f"{currency}_{title}_{timestamp_utc}".replace(" ", "_")

        parsed_events.append({
            "event_id": event_id,
            "title": title,
            "currency": currency,
            "impact": "high",
            "timestamp_utc": timestamp_utc,
            "event_timestamp": timestamp_utc,
            "forecast": forecast,
            "previous": previous,
            "time_str": dt.strftime("%H:%M UTC"),
            "date_str": dt.strftime("%Y-%m-%d"),
        })

    return parsed_events
