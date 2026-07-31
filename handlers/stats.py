import logging
from datetime import date, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database import Database
from stats_engine import compute_statistics, format_stats_report, compute_group_breakdown

logger = logging.getLogger(__name__)
cfg = Config()
db = Database(cfg.DB_PATH, cfg)


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    today_dt = date.today()
    trades = db.trades_in_period(today_dt, today_dt)
    stats = compute_statistics(trades)
    report = format_stats_report(f"DAILY TRADING STATISTICS ({today_dt.isoformat()})", stats)
    await target.reply_text(report, parse_mode="Markdown")


async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    end = date.today()
    start = end - timedelta(days=7)
    trades = db.trades_in_period(start, end)
    stats = compute_statistics(trades)
    report = format_stats_report("WEEKLY TRADING STATISTICS (7 HARI TERAKHIR)", stats)
    await target.reply_text(report, parse_mode="Markdown")


async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    today_dt = date.today()
    start = date(today_dt.year, today_dt.month, 1)
    end = today_dt
    trades = db.trades_in_period(start, end)
    stats = compute_statistics(trades)
    report = format_stats_report(f"MONTHLY TRADING STATISTICS ({today_dt.strftime('%B %Y')})", stats)
    await target.reply_text(report, parse_mode="Markdown")


async def yearly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    today_dt = date.today()
    start = date(today_dt.year, 1, 1)
    end = today_dt
    trades = db.trades_in_period(start, end)
    stats = compute_statistics(trades)
    report = format_stats_report(f"YEARLY TRADING STATISTICS ({today_dt.year})", stats)
    await target.reply_text(report, parse_mode="Markdown")


async def overall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    trades = db.get_all_trades()
    stats = compute_statistics(trades)
    report = format_stats_report("OVERALL TRADING STATISTICS (ALL-TIME)", stats)
    await target.reply_text(report, parse_mode="Markdown")


async def pair_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    trades = db.get_all_trades()
    if not trades:
        await target.reply_text("Belum ada trade yang tercatat.")
        return

    breakdown = compute_group_breakdown(trades, "pair")
    text = "📊 *PERFORMANCE BY CURRENCY PAIR*\n━━━━━━━━━━━━━━━━━━━\n\n"
    for pair, s in sorted(breakdown.items(), key=lambda x: x[1]["net_r"], reverse=True):
        text += (
            f"🔀 *{pair}*\n"
            f"• Closed Trades: `{s['total']}` | Win Rate: `{s['win_rate']}%`\n"
            f"• Wins: `{s['wins']}` | Losses: `{s['losses']}` | BE: `{s['be']}`\n"
            f"• Net R: `{s['net_r']:+}R` | PF: `{s['profit_factor']}`\n\n"
        )
    await target.reply_text(text, parse_mode="Markdown")


async def weekday_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    trades = db.get_all_trades()
    if not trades:
        await target.reply_text("Belum ada trade yang tercatat.")
        return

    breakdown = compute_group_breakdown(trades, "weekday")
    text = "📅 *PERFORMANCE BY WEEKDAY*\n━━━━━━━━━━━━━━━━━━━\n\n"
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for day in days_order:
        if day in breakdown:
            s = breakdown[day]
            text += (
                f"📆 *{day}*\n"
                f"• Closed Trades: `{s['total']}` | Win Rate: `{s['win_rate']}%`\n"
                f"• Net R: `{s['net_r']:+}R` | PF: `{s['profit_factor']}`\n\n"
            )
    await target.reply_text(text, parse_mode="Markdown")


async def month_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    trades = db.get_all_trades()
    if not trades:
        await target.reply_text("Belum ada trade yang tercatat.")
        return

    breakdown = compute_group_breakdown(trades, "month")
    text = "🗓️ *PERFORMANCE BY MONTH*\n━━━━━━━━━━━━━━━━━━━\n\n"
    for m, s in breakdown.items():
        text += (
            f"🗓️ *{m}*\n"
            f"• Closed Trades: `{s['total']}` | Win Rate: `{s['win_rate']}%`\n"
            f"• Net R: `{s['net_r']:+}R` | PF: `{s['profit_factor']}`\n\n"
        )
    await target.reply_text(text, parse_mode="Markdown")


async def today_trades_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    today_iso = date.today().isoformat()
    trades = db.trades_in_period(date.today(), date.today())
    if not trades:
        await target.reply_text("ℹ️ Tidak ada trade hari ini.")
        return

    text = f"📋 *TRADES HARI INI ({today_iso}):*\n━━━━━━━━━━━━━━━━━━━\n\n"
    for t in trades:
        res = t.get("result") or t.get("status") or "OPEN"
        r_val = f"{t.get('actual_r'):+}R" if t.get('actual_r') is not None else f"{t.get('planned_rr')}R (Planned)"
        trade_id = t.get('id')
        code = t.get('trade_code', f'#{trade_id}')
        text += f"• `{code}` | *{t['pair']}* {t['direction']} | Outcome: `{res}` ({r_val})\n"

    await target.reply_text(text, parse_mode="Markdown")


async def delete_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message
    args = context.args or []
    if not args:
        await target.reply_text("Format salah. Gunakan: `/delete <id_or_trade_code>`", parse_mode="Markdown")
        return

    raw_id = args[0].replace("#TRADE-", "").replace("#", "")
    try:
        tid = int(raw_id)
    except ValueError:
        await target.reply_text("❌ ID tidak valid.")
        return

    trade = db.get_trade_by_id(tid)
    if not trade:
        await target.reply_text("❌ Trade tidak ditemukan.")
        return

    db.delete_trade(tid)
    trade_code = trade.get('trade_code', f'#{tid}')
    await target.reply_text(f"✅ Trade `{trade_code}` berhasil dihapus.", parse_mode="Markdown")
