import logging
import asyncio
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import Config
from database import Database
from scraper import fetch_calendar

logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """Escapes special markdown characters to prevent Telegram parse errors."""
    if not text:
        return ""
    for char in ["*", "_", "`", "["]:
        text = text.replace(char, f"\\{char}")
    return text


class NewsScheduler:
    def __init__(self, application: Application, config: Optional[Config] = None, database: Optional[Database] = None):
        self.app = application
        self.cfg = config or Config()
        self.db = database or Database(self.cfg.DB_PATH, self.cfg)
        self.tz = ZoneInfo(self.cfg.TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)

    def start(self):
        """
        Starts APScheduler background jobs.
        """
        # 1. Background news scraping refresh (every 30 minutes)
        self.scheduler.add_job(
            self.refresh_news_cache_job,
            trigger=IntervalTrigger(minutes=30),
            id="refresh_news_cache",
            replace_existing=True,
        )

        # 2. Weekly News Summary every Monday at 07:00 Asia/Jakarta
        self.scheduler.add_job(
            self.send_weekly_news_broadcast,
            trigger=CronTrigger(day_of_week="mon", hour=7, minute=0, timezone=self.tz),
            id="weekly_news_broadcast",
            replace_existing=True,
        )

        # 3. Check for H-2 and H-1 reminders every 1 minute
        self.scheduler.add_job(
            self.check_news_reminders,
            trigger=IntervalTrigger(minutes=1),
            id="check_news_reminders",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("APScheduler started successfully for News Reminders & Weekly Broadcast.")

    def stop(self):
        """Stops the scheduler gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped.")

    async def refresh_news_cache_job(self):
        logger.info("Running periodic news cache refresh...")
        try:
            await fetch_calendar(self.cfg, self.db)
        except Exception as e:
            logger.error(f"Error in refresh_news_cache_job: {e}")

    async def send_weekly_news_broadcast(self):
        """
        Sends the weekly economic calendar broadcast to the target channel/chat every Monday 07:00 WIB.
        """
        target_chat = self.cfg.TARGET_CHAT_ID or self.cfg.BOT_OWNER_ID
        if not target_chat:
            logger.warning("No TARGET_CHAT_ID or BOT_OWNER_ID configured for weekly broadcast.")
            return

        logger.info(f"Triggering Weekly News Broadcast to chat {target_chat}...")
        try:
            events = await fetch_calendar(self.cfg, self.db)
            if not events:
                await self.app.bot.send_message(
                    chat_id=target_chat,
                    text="📅 *WEEKLY ECONOMIC CALENDAR*\n\nTidak ada High Impact news untuk minggu ini.",
                    parse_mode="Markdown",
                )
                return

            by_currency = {}
            for e in events:
                curr = e.get("currency", "OTHER")
                by_currency.setdefault(curr, []).append(e)

            text = "📅 *WEEKLY HIGH IMPACT ECONOMIC CALENDAR*\n"
            text += f"🕒 *Minggu Ini ({datetime.now(self.tz).strftime('%d %b %Y')})*\n"
            text += "━━━━━━━━━━━━━━━━━━━\n\n"

            for curr in self.cfg.WATCHED_CURRENCIES:
                curr_events = by_currency.get(curr, [])
                if not curr_events:
                    continue
                text += f"🚩 *Currency: {curr}*\n"
                for ev in sorted(curr_events, key=lambda x: x.get("timestamp_utc") or x.get("event_timestamp") or 0):
                    ts = ev.get("timestamp_utc") or ev.get("event_timestamp") or 0
                    local_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(self.tz)
                    time_fmt = local_dt.strftime("%a %H:%M WIB")
                    title_safe = escape_markdown(ev.get("title", ""))
                    text += f"• `{time_fmt}` | *{title_safe}*\n"
                text += "\n"

            await self.app.bot.send_message(
                chat_id=target_chat,
                text=text,
                parse_mode="Markdown",
            )
            logger.info("Weekly news broadcast sent successfully.")
        except Exception as e:
            logger.exception(f"Error sending weekly news broadcast: {e}")

    async def check_news_reminders(self):
        """
        Checks for upcoming news events (H-2, H-1 reminders) and real-time Actual Data Releases.
        """
        target_chat = self.cfg.TARGET_CHAT_ID or self.cfg.BOT_OWNER_ID
        if not target_chat:
            return

        try:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            events = self.db.get_news_events()
            if not events:
                events = await fetch_calendar(self.cfg, self.db)

            pending_actual_check = []

            for ev in events:
                event_id = ev.get("event_id")
                event_ts = ev.get("timestamp_utc") or ev.get("event_timestamp") or 0
                if not event_ts or not event_id:
                    continue

                diff_seconds = event_ts - now_ts
                diff_minutes = diff_seconds // 60

                # 1. Check H-2 Reminder (110 to 125 minutes window)
                if 110 <= diff_minutes <= 125:
                    if not self.db.is_notification_sent(event_id, "H-2"):
                        await self.send_reminder(target_chat, ev, "H-2 (2 Jam)", diff_minutes)
                        self.db.mark_notification_sent(event_id, "H-2")

                # 2. Check H-1 Reminder (50 to 65 minutes window)
                if 50 <= diff_minutes <= 65:
                    if not self.db.is_notification_sent(event_id, "H-1"):
                        await self.send_reminder(target_chat, ev, "H-1 (1 Jam)", diff_minutes)
                        self.db.mark_notification_sent(event_id, "H-1")

                # 3. Collect events that occurred in the last 2 hours and haven't sent ACTUAL notification
                if 0 <= -diff_seconds <= 7200:
                    if not self.db.is_notification_sent(event_id, "ACTUAL"):
                        pending_actual_check.append(ev)

            # If there are events waiting for actual release, fetch fresh data from TradingView API
            if pending_actual_check:
                fresh_events = await fetch_calendar(self.cfg, self.db)
                fresh_dict = {e["event_id"]: e for e in fresh_events if "event_id" in e}

                for ev in pending_actual_check:
                    event_id = ev.get("event_id")
                    fresh_ev = fresh_dict.get(event_id) or ev
                    actual_val = fresh_ev.get("actual")

                    if actual_val and str(actual_val).strip() not in ("-", "", "None"):
                        await self.send_actual_release_notification(target_chat, fresh_ev)
                        self.db.mark_notification_sent(event_id, "ACTUAL")

        except Exception as e:
            logger.exception(f"Error in check_news_reminders loop: {e}")

    async def send_reminder(self, chat_id: str, event: dict, tag: str, diff_minutes: int):
        ts = event.get("timestamp_utc") or event.get("event_timestamp") or 0
        local_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(self.tz)
        day_str = local_dt.strftime("%A, %d %B %Y")
        time_str = local_dt.strftime("%H:%M WIB")

        hours = diff_minutes // 60
        mins = diff_minutes % 60
        remaining_str = f"{hours} Jam {mins} Menit" if hours > 0 else f"{mins} Menit"
        title_safe = escape_markdown(event.get("title", ""))

        text = (
            f"🚨 *HIGH IMPACT NEWS REMINDER ({tag})* 🚨\n\n"
            f"🚩 *Currency:* `{event.get('currency')}`\n"
            f"📰 *Event:* *{title_safe}*\n"
            f"🕒 *Waktu Event:* `{day_str}` pukul `{time_str}`\n"
            f"📊 *Forecast:* `{event.get('forecast', '-')}` | *Previous:* `{event.get('previous', '-')}`\n\n"
            f"⏳ *Sisa Waktu:* `{remaining_str}`"
        )

        try:
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
            )
            logger.info(f"Sent {tag} news reminder for event: {event.get('title')}")
        except Exception as err:
            logger.error(f"Failed to send reminder for {event.get('title')}: {err}")

    async def send_actual_release_notification(self, chat_id: str, event: dict):
        ts = event.get("timestamp_utc") or event.get("event_timestamp") or 0
        local_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(self.tz)
        day_str = local_dt.strftime("%A, %d %B %Y")
        time_str = local_dt.strftime("%H:%M WIB")

        title_safe = escape_markdown(event.get("title", ""))
        actual_val = escape_markdown(str(event.get("actual", "-")))
        forecast_val = escape_markdown(str(event.get("forecast", "-")))
        previous_val = escape_markdown(str(event.get("previous", "-")))

        text = (
            f"📢 *ECONOMIC NEWS ACTUAL DATA RELEASED* 📢\n\n"
            f"🚩 *Currency:* `{event.get('currency')}`\n"
            f"📰 *Event:* *{title_safe}*\n"
            f"🕒 *Waktu Event:* `{day_str}` pukul `{time_str}`\n\n"
            f"📊 *Actual:* `{actual_val}` 💥\n"
            f"🎯 *Forecast:* `{forecast_val}`\n"
            f"📁 *Previous:* `{previous_val}`"
        )

        try:
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
            )
            logger.info(f"Sent actual release notification for event: {event.get('title')} (Actual: {actual_val})")
        except Exception as err:
            logger.error(f"Failed to send actual release notification for {event.get('title')}: {err}")
