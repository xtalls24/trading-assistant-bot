import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database import Database
from scraper import fetch_calendar

logger = logging.getLogger(__name__)
cfg = Config()
db = Database(cfg.DB_PATH, cfg)


def get_ts(e: dict) -> int:
    return e.get("timestamp_utc") or e.get("event_timestamp") or 0


def format_event_card(event: dict, local_dt: datetime) -> str:
    day_str = local_dt.strftime("%A, %d %b %Y")
    time_str = local_dt.strftime("%H:%M WIB")
    now_local = datetime.now(local_dt.tzinfo)
    minutes_left = max(0, int((local_dt - now_local).total_seconds() // 60))
    hours = minutes_left // 60
    mins = minutes_left % 60
    time_remaining_str = f"{hours} Jam {mins} Menit" if hours > 0 else f"{mins} Menit"

    return (
        f"🚨 *HIGH IMPACT NEWS EVENT*\n\n"
        f"🚩 *Currency:* `{event.get('currency')}`\n"
        f"📰 *Event:* *{event.get('title')}*\n\n"
        f"🕒 *Waktu:* `{day_str}` - `{time_str}`\n"
        f"📊 *Forecast:* `{event.get('forecast', '-')}`\n"
        f"📈 *Previous:* `{event.get('previous', '-')}`\n\n"
        f"⏳ *Sisa Waktu:* `{time_remaining_str}`"
    )


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    msg = await target.reply_text("🔎 *Mencari jadwal High Impact News berikutnya...*", parse_mode="Markdown")
    try:
        events = await fetch_calendar(cfg, db)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        future = [e for e in events if get_ts(e) >= now_ts]

        if not future:
            await msg.edit_text("ℹ️ Tidak ada event High Impact (Red Folder) berikutnya untuk minggu ini.")
            return

        next_event = sorted(future, key=get_ts)[0]
        tz = ZoneInfo(cfg.TIMEZONE)
        local_dt = datetime.fromtimestamp(get_ts(next_event), tz=timezone.utc).astimezone(tz)
        await msg.edit_text(format_event_card(next_event, local_dt), parse_mode="Markdown")
    except Exception as err:
        logger.exception("Error in cmd_next")
        await msg.edit_text(f"❌ Terjadi kesalahan: {err}")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    msg = await target.reply_text("🔎 *Mengambil berita High Impact hari ini...*", parse_mode="Markdown")
    try:
        events = await fetch_calendar(cfg, db)
        tz = ZoneInfo(cfg.TIMEZONE)
        today_date = datetime.now(tz).date()

        today_events = []
        for e in events:
            ts = get_ts(e)
            if not ts:
                continue
            local_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
            if local_dt.date() == today_date:
                today_events.append((local_dt, e))

        if not today_events:
            await msg.edit_text("ℹ️ Tidak ada High Impact News hari ini.")
            return

        text = "🚨 *HIGH IMPACT NEWS HARI INI:*\n\n"
        for local_dt, e in sorted(today_events, key=lambda x: x[0]):
            time_fmt = local_dt.strftime("%H:%M WIB")
            text += f"• `{time_fmt}` | *{e['currency']}* - {e['title']} (FC: `{e.get('forecast','-')}`)\n"

        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as err:
        logger.exception("Error in cmd_today")
        await msg.edit_text(f"❌ Terjadi kesalahan: {err}")


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    msg = await target.reply_text("🔎 *Mengambil jadwal High Impact News minggu ini...*", parse_mode="Markdown")
    try:
        events = await fetch_calendar(cfg, db)
        if not events:
            await msg.edit_text("ℹ️ Tidak ada High Impact News minggu ini.")
            return

        tz = ZoneInfo(cfg.TIMEZONE)
        text = "📅 *HIGH IMPACT NEWS MINGGU INI:*\n━━━━━━━━━━━━━━━━━━━\n\n"
        for e in sorted(events, key=get_ts):
            ts = get_ts(e)
            if not ts:
                continue
            local_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
            time_fmt = local_dt.strftime("%a %d %b, %H:%M WIB")
            text += f"• `{time_fmt}` | *{e['currency']}* - {e['title']}\n"

        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as err:
        logger.exception("Error in cmd_week")
        await msg.edit_text(f"❌ Terjadi kesalahan: {err}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trades = db.get_all_trades()
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    news = db.get_news_events()

    text = (
        "🤖 *TRADING ASSISTANT BOT STATUS*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🟢 *Bot Status:* `ONLINE & ACTIVE`\n"
        f"📊 *Total Trades Saved:* `{len(trades)}`\n"
        f"🔓 *Open Trades:* `{len(open_trades)}`\n"
        f"📰 *Cached News Events:* `{len(news)}`\n"
        f"🕒 *Timezone:* `{cfg.TIMEZONE}`\n"
        f"🚩 *Watched Currencies:* `{', '.join(cfg.WATCHED_CURRENCIES)}`"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")
