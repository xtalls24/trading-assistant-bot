import logging
from telegram import Update
from telegram.ext import ContextTypes
from database import Database
from config import Config
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

cfg = Config()
db = Database("database.db", cfg)


def _format_stats(rows):
    s = db.stats_for_rows(rows)
    return (
        f"Total Trade: {s['total']}\n"
        f"TP: {s['tp']}\n"
        f"SL: {s['sl']}\n"
        f"Winrate: {s['winrate']}%\n"
        f"Total R: {s['total_r']}\n"
    )


async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    end = date.today()
    start = end - timedelta(days=7)
    rows = db.trades_in_period(start, end)
    text = "Weekly stats:\n" + _format_stats(rows)

    # breakdown by model
    models = {}
    for r in rows:
        models.setdefault(r['model'], 0)
        models[r['model']] += float(r.get('rr') or 0)
    text += "\nBreakdown by Model:\n"
    for m, val in models.items():
        text += f"{m} : {val:+}R\n"

    await update.message.reply_text(text)


async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    start = date(today.year, today.month, 1)
    end = today
    rows = db.trades_in_period(start, end)
    text = "Monthly stats:\n" + _format_stats(rows)
    models = {}
    for r in rows:
        models.setdefault(r['model'], 0)
        models[r['model']] += float(r.get('rr') or 0)
    text += "\nBreakdown by Model:\n"
    for m, val in models.items():
        text += f"{m} : {val:+}R\n"
    await update.message.reply_text(text)


async def pair_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("Gunakan /pair EURUSD")
        return
    pair = args[0].upper()
    rows = db.query("WHERE pair=?", (pair,))
    text = f"Stats untuk {pair}:\n" + _format_stats(rows)
    await update.message.reply_text(text)


async def model_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("Gunakan /model C1")
        return
    model = args[0].upper()
    rows = db.query("WHERE model=?", (model,))
    text = f"Stats untuk {model}:\n" + _format_stats(rows)
    await update.message.reply_text(text)


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today().isoformat()
    rows = db.query("WHERE date=? ORDER BY date", (today,))
    if not rows:
        await update.message.reply_text("Tidak ada trade hari ini")
        return
    text = "Trades hari ini:\n"
    for r in rows:
        text += f"ID:{r['id']} {r['pair']} {r['direction']} {r['result']} RR:{r['rr']}\n"
    await update.message.reply_text(text)


async def delete_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("Gunakan /delete <id>")
        return
    try:
        tid = int(args[0])
    except Exception:
        await update.message.reply_text("ID tidak valid")
        return
    trade = db.get_trade(tid)
    if not trade:
        await update.message.reply_text("Trade tidak ditemukan")
        return
    db.delete_trade(tid)
    await update.message.reply_text(f"Trade {tid} dihapus")
