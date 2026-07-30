import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes
from ffnews.scraper import fetch_calendar
from config import Config

logger = logging.getLogger(__name__)
cfg = Config()

def to_local(ts_utc: int) -> datetime:
    tz = ZoneInfo(cfg.TIMEZONE)
    return datetime.fromtimestamp(ts_utc, tz=timezone.utc).astimezone(tz)

def format_event_message(event, local_dt):
    day = local_dt.strftime("%A")
    date_str = local_dt.strftime("%d %B %Y")
    time_str = local_dt.strftime("%H:%M")
    now_local = datetime.now(local_dt.tzinfo)
    minutes_left = max(0, int((local_dt - now_local).total_seconds() // 60))
    hours = minutes_left // 60
    mins = minutes_left % 60
    
    time_remaining_str = f"{hours} Jam {mins} Menit" if hours > 0 else f"{mins} Menit"
    forecast_val = event.get("forecast") or "-"
    previous_val = event.get("previous") or "-"

    return (
        "🚨 RED FOLDER ALERT 🚨\n\n"
        f"Currency: {event.get(currency, )}\n"
        f"📰 Event: {event.get(title)}\n\n"
        f"🕒 Waktu: {day}, {date_str} - {time_str} WIB\n"
        f"📊 Forecast: {forecast_val}\n"
        f"📈 Previous: {previous_val}\n\n"
        f"⏳ Sisa waktu: {time_remaining_str}"
    )

async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔎 Mencari jadwal High Impact News berikutnya...")
    try:
        events = await fetch_calendar(cfg)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        future = [e for e in events if e.get("timestamp_utc", 0) >= now_ts]
        
        if not future:
            await msg.edit_text("❌ Tidak ada event High Impact (Red Folder) berikutnya untuk minggu ini.")
            return
            
        e = sorted(future, key=lambda x: x["timestamp_utc"])[0]
        local = to_local(e["timestamp_utc"])
        await msg.edit_text(format_event_message(e, local))
    except Exception as err:
        logger.exception("Error in cmd_next")
        await msg.edit_text(f"❌ Terjadi kesalahan saat mengambil berita: {err}")

async def cmd_news_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔎 Mengambil berita High Impact hari ini...")
    try:
        events = await fetch_calendar(cfg)
        tz = ZoneInfo(cfg.TIMEZONE)
        today = datetime.now(tz).date()
        out = []
        for e in events:
            local = to_local(e["timestamp_utc"])
            if local.date() == today:
                out.append((local, e))
        if not out:
            await msg.edit_text("ℹ️ Tidak ada High Impact News hari ini.")
            return
        text = "🚨 *High Impact News Hari Ini:*\n\n"
        for local, e in sorted(out):
            time_formatted = local.strftime("%H:%M")
            text += f"• *{time_formatted} WIB* | {e[currency]} - {e[title]}\n"
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as err:
        logger.exception("Error in cmd_news_today")
        await msg.edit_text(f"❌ Terjadi kesalahan: {err}")
