import requests
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any
from config import cfg

logger = logging.getLogger(__name__)


def fetch_calendar() -> List[Dict[str, Any]]:
    """Fetch the Forex Factory calendar JSON and return a list of event dicts.

    The exact JSON structure may vary; this function attempts to be robust.
    Each returned event will include at least: id, title, impact, currency, timestamp_utc
    """
    try:
        r = requests.get(cfg.NEWS_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.exception("Failed to fetch calendar: %s", e)
        return []

    events = []

    # Common shapes: list of events or dict with 'events' key
    if isinstance(data, dict):
        candidates = data.get("events") or data.get("rows") or data.get("calendar") or data.get("data")
        if candidates is None:
            # maybe dict of dates
            for k, v in data.items():
                if isinstance(v, list):
                    candidates = v
                    break
    else:
        candidates = data

    if not candidates:
        logger.debug("No candidates found in fetched JSON")
        return []

    for item in candidates:
        try:
            # try common fields
            event_id = str(item.get("id") or item.get("event_id") or item.get("key") or item.get("E"))
            title = item.get("title") or item.get("event") or item.get("headline") or "Unknown"
            impact = (item.get("impact") or item.get("importance") or "").lower()
            currency = (item.get("currency") or item.get("country") or "").upper()

            # timestamp fields may differ
            ts = None
            if item.get("timestamp"):
                ts = int(item.get("timestamp"))
            elif item.get("time"):
                # try ISO string
                try:
                    dt = datetime.fromisoformat(item.get("time"))
                    ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
                except Exception:
                    ts = None

            if ts is None and item.get("date") and item.get("time"):
                try:
                    iso = f"{item.get('date')}T{item.get('time')}Z"
                    dt = datetime.fromisoformat(iso)
                    ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
                except Exception:
                    ts = None

            if ts is None:
                # skip if no timestamp
                continue

            events.append(
                {
                    "id": event_id,
                    "title": title,
                    "impact": impact,
                    "currency": currency,
                    "timestamp_utc": ts,
                    "raw": item,
                }
            )
        except Exception:
            logger.exception("Failed parse event")
            continue

    return events


def to_local(dt_utc_ts: int):
    tz = ZoneInfo(cfg.TIMEZONE)
    return datetime.fromtimestamp(dt_utc_ts, tz=timezone.utc).astimezone(tz)
