import logging
from telegram import Update
from telegram.ext import ContextTypes
from news import fetch_calendar, to_local
from database import Database
from config import cfg
from datetime import date, timedelta

logger = logging.getLogger(__name__)
db = Database("ffnews.db")


def format_event_message(event, local_dt):
    day = local_dt.strftime("%A")
    date_str = local_dt.strftime("%d %B %Y")
    time_str = local_dt.strftime("%H:%M")
    minutes_left = int((local_dt - local_dt.now(local_dt.tzinfo)).total_seconds() // 60)
    # compute remaining time more meaningfully
    return (
        "🚨 RED FOLDER ALERT\n\n"
        f"{event.get('currency', '')}\n\n"
        f"📰 {event.get('title')}\n\n"
        "🕒\n"
        f"{day}\n"
        f"{date_str}\n"
        f"{time_str} WIB\n\n"
        f"Forecast : {event.get('raw', {}).get('forecast', '')}\n\n"
        f"Previous : {event.get('raw', {}).get('previous', '')}\n\n"
        f"Sisa waktu: {minutes_left // 60} Jam"
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = fetch_calendar()
    tz = cfg.TIMEZONE
    today = date.today()
    out = []
    for e in events:
        if e["impact"] != "high" and "red" not in e["impact"]:
            continue
        if e["currency"] not in ("USD", "AUD"):
            continue
        local = to_local(e["timestamp_utc"])
        if local.date() == today:
            out.append((local, e))
    if not out:
        await update.message.reply_text("Tidak ada High Impact hari ini.")
        return
    text = "High Impact hari ini:\n"
    for local, e in sorted(out):
        text += f"{e['currency']} {e['title']} {local.strftime('%H:%M')} WIB\n"
    await update.message.reply_text(text)


async def cmd_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = fetch_calendar()
    tomorrow = date.today() + timedelta(days=1)
    out = []
    for e in events:
        if e["impact"] != "high" and "red" not in e["impact"]:
            continue
        if e["currency"] not in ("USD", "AUD"):
            continue
        local = to_local(e["timestamp_utc"])
        if local.date() == tomorrow:
            out.append((local, e))
    if not out:
        await update.message.reply_text("Tidak ada High Impact besok.")
        return
    text = "High Impact besok:\n"
    for local, e in sorted(out):
        text += f"{e['currency']} {e['title']} {local.strftime('%d %b %H:%M')} WIB\n"
    await update.message.reply_text(text)


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = fetch_calendar()
    today = date.today()
    end = today + timedelta(days=7)
    out = []
    for e in events:
        if e["impact"] != "high" and "red" not in e["impact"]:
            continue
        if e["currency"] not in ("USD", "AUD"):
            continue
        local = to_local(e["timestamp_utc"])
        if today <= local.date() <= end:
            out.append((local, e))
    if not out:
        await update.message.reply_text("Tidak ada High Impact minggu ini.")
        return
    text = "High Impact minggu ini:\n"
    for local, e in sorted(out):
        text += f"{local.strftime('%a %d %b %H:%M')} {e['currency']} {e['title']}\n"
    await update.message.reply_text(text)


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = fetch_calendar()
    future = []
    now_ts = int(datetime.utcnow().timestamp())
    for e in events:
        if e["impact"] != "high" and "red" not in e["impact"]:
            continue
        if e["currency"] not in ("USD", "AUD"):
            continue
        if e["timestamp_utc"] >= now_ts:
            future.append(e)
    if not future:
        await update.message.reply_text("Tidak ada event Red Folder berikutnya.")
        return
    e = sorted(future, key=lambda x: x["timestamp_utc"])[0]
    local = to_local(e["timestamp_utc"])
    await update.message.reply_text(format_event_message(e, local))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    events = fetch_calendar()
    now = datetime.utcnow().isoformat()
    count = 0
    for e in events:
        if e["impact"] != "high" and "red" not in e["impact"]:
            continue
        if e["currency"] not in ("USD", "AUD"):
            continue
        count += 1
    text = f"Bot Online ✅\n\nLast Update: {now} UTC\nJumlah event minggu ini: {count}"
    await update.message.reply_text(text)
