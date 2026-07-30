import asyncio
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from news import fetch_calendar, to_local
from database import Database
from telegram import Bot
from config import cfg

logger = logging.getLogger(__name__)
db = Database("ffnews.db")


class Scheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self._task = None

    async def _run(self):
        tz = ZoneInfo(cfg.TIMEZONE)
        while True:
            try:
                events = fetch_calendar()
                now_local = datetime.now(tz)
                now_ts = int(datetime.now(timezone.utc).timestamp())
                for e in events:
                    # only high impact
                    impact = e.get("impact", "").lower()
                    if not (impact == "high" or "red" in impact):
                        continue
                    currency = e.get("currency", "").upper()
                    if currency not in ("USD", "AUD"):
                        continue

                    ev_ts = int(e.get("timestamp_utc"))
                    ev_local = to_local(ev_ts)
                    delta = ev_local - now_local
                    minutes = int(delta.total_seconds() // 60)

                    # thresholds: ±5 minutes window around 120 and 60 minutes
                    status = db.get_status(e["id"]) or {}
                    # H-2
                    if 115 <= minutes <= 125 and not status.get("h2_sent"):
                        text = f"[AUTO] H-2: {e.get('currency')} {e.get('title')} at {ev_local.strftime('%Y-%m-%d %H:%M')}"
                        await self.bot.send_message(chat_id=self.bot.owner_id, text=text)
                        db.mark_sent(e["id"], "h2")
                        logger.info("Sent H-2 for %s", e["id"])

                    # H-1
                    if 55 <= minutes <= 65 and not status.get("h1_sent"):
                        text = f"[AUTO] H-1: {e.get('currency')} {e.get('title')} at {ev_local.strftime('%Y-%m-%d %H:%M')}"
                        await self.bot.send_message(chat_id=self.bot.owner_id, text=text)
                        db.mark_sent(e["id"], "h1")
                        logger.info("Sent H-1 for %s", e["id"])

            except Exception:
                logger.exception("Error in scheduler loop")
            await asyncio.sleep(cfg.CHECK_INTERVAL_SECONDS)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run())
