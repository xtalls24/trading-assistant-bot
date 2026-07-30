import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from scraper import fetch_calendar

logger = logging.getLogger(__name__)

cfg = Config()


def _to_local(ts_utc: int) -> datetime:
    tz = ZoneInfo(cfg.TIMEZONE)
    return datetime.fromtimestamp(ts_utc, tz=timezone.utc).astimezone(tz)


def _format_event_line(event: dict) -> str:
    local = _to_local(event["timestamp_utc"])
    return f"{local.strftime('%H:%M')} WIB | {event['currency']} | {event['title']}"


def _format_event_detail(event: dict) -> str:
    local = _to_local(event["timestamp_utc"])
    return (
        "🚨 HIGH IMPACT EVENT\n\n"
        f"{event['currency']}\n\n"
        f"📰 {event['title']}\n\n"
        f"🕒 {local.strftime('%A, %d %B %Y %H:%M')} WIB\n\n"
        f"Forecast : {event.get('forecast') or '-'}\n"
        f"Previous : {event.get('previous') or '-'}\n"
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    events = await fetch_calendar()
    today = date.today()
    todays = sorted(
        (e for e in events if _to_local(e["timestamp_utc"]).date() == today),
        key=lambda e: e["timestamp_utc"],
    )

    if not todays:
        await update.message.reply_text("Tidak ada event High Impact hari ini.")
        return

    text = "📅 High Impact hari ini:\n\n" + "\n".join(_format_event_line(e) for e in todays)
    await update.message.reply_text(text)


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    events = await fetch_calendar()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    upcoming = sorted(
        (e for e in events if e["timestamp_utc"] >= now_ts),
        key=lambda e: e["timestamp_utc"],
    )

    if not upcoming:
        await update.message.reply_text("Tidak ada event High Impact berikutnya.")
        return

    await update.message.reply_text(_format_event_detail(upcoming[0]))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    events = await fetch_calendar()
    now = datetime.now(timezone.utc).isoformat()

    status_line = "✅ Online" if events or True else "⚠️ Scraper returned no data"
    text = (
        f"Bot Status: {status_line}\n\n"
        f"Last check (UTC): {now}\n"
        f"High impact events this week: {len(events)}\n"
        f"Watched currencies: {', '.join(cfg.WATCHED_CURRENCIES)}"
    )
    await update.message.reply_text(text)
