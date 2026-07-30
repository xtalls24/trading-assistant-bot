import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import Bot

from config import Config
from database import Database
from scraper import fetch_calendar

logger = logging.getLogger(__name__)


class Scheduler:
    """Periodically scrapes the calendar and sends H-2 / H-1 alerts.

    Fixes vs. the old ffnews implementation:
    - `bot.owner_id` was referenced but never set anywhere, so every send
      attempt would raise AttributeError and crash the scheduler loop
      silently (caught only by the broad except, but no message ever sent).
      Now the chat id comes from Config.BOT_OWNER_ID.
    - A `_running` guard prevents two poll cycles from overlapping if a
      scrape takes longer than CHECK_INTERVAL_SECONDS, which previously
      could launch a second Playwright browser concurrently.
    - Notification dedupe is unchanged in spirit (SQLite-backed) but now
      shares the single project-wide Database/connection helper.
    """

    def __init__(self, bot: Bot, db: Database, cfg: Config):
        self.bot = bot
        self.db = db
        self.cfg = cfg
        self._task = None
        self._running = False

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("Calendar scheduler started")

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        while True:
            if self._running:
                logger.warning("Previous scheduler cycle still running; skipping this tick")
            else:
                self._running = True
                try:
                    await self._check_once()
                except Exception:
                    logger.exception("Unhandled error in scheduler cycle")
                finally:
                    self._running = False
            await asyncio.sleep(self.cfg.CHECK_INTERVAL_SECONDS)

    async def _check_once(self) -> None:
        if not self.cfg.BOT_OWNER_ID:
            logger.warning("BOT_OWNER_ID not configured; skipping notification check")
            return

        events = await fetch_calendar(self.cfg)
        if not events:
            logger.info("No events returned this cycle (scrape empty or failed)")
            return

        tz = ZoneInfo(self.cfg.TIMEZONE)
        now_local = datetime.now(tz)

        for event in events:
            event_dt = datetime.fromtimestamp(event["timestamp_utc"], tz=timezone.utc).astimezone(tz)
            minutes_left = int((event_dt - now_local).total_seconds() // 60)
            status = self.db.get_notification_status(event["id"]) or {}

            if 115 <= minutes_left <= 125 and not status.get("h2_sent"):
                await self._send_alert(event, event_dt, "H-2")
                self.db.mark_sent(event["id"], "h2")

            if 55 <= minutes_left <= 65 and not status.get("h1_sent"):
                await self._send_alert(event, event_dt, "H-1")
                self.db.mark_sent(event["id"], "h1")

    async def _send_alert(self, event: dict, event_dt: datetime, label: str) -> None:
        text = (
            f"⏰ {label} ALERT\n\n"
            f"{event['currency']} — {event['title']}\n"
            f"Waktu: {event_dt.strftime('%A, %d %B %Y %H:%M')} WIB\n"
            f"Forecast: {event.get('forecast') or '-'}\n"
            f"Previous: {event.get('previous') or '-'}"
        )
        try:
            await self.bot.send_message(chat_id=self.cfg.BOT_OWNER_ID, text=text)
            logger.info("Sent %s alert for event %s", label, event["id"])
        except Exception:
            logger.exception("Failed to send %s alert for event %s", label, event["id"])
