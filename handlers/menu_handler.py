import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import Config
from database import Database
from handlers import news_handler, stats

logger = logging.getLogger(__name__)
cfg = Config()
db = Database(cfg.DB_PATH, cfg)


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📖 Trading Journal", callback_data="menu_journal"),
            InlineKeyboardButton("📅 Economic News", callback_data="menu_news"),
        ],
        [
            InlineKeyboardButton("📊 Statistics", callback_data="menu_stats"),
            InlineKeyboardButton("⚙️ Settings & Status", callback_data="menu_settings"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_journal_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📋 Today's Trades", callback_data="journal_today"),
            InlineKeyboardButton("🔓 Open Trades", callback_data="journal_open"),
        ],
        [
            InlineKeyboardButton("📜 Recent Trades", callback_data="journal_recent"),
        ],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_news_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🚨 Today's News", callback_data="news_today"),
            InlineKeyboardButton("📅 This Week", callback_data="news_week"),
        ],
        [
            InlineKeyboardButton("⏳ Next High Impact", callback_data="news_next"),
            InlineKeyboardButton("🔄 Refresh Cache", callback_data="news_refresh"),
        ],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_stats_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📅 Daily", callback_data="stats_daily"),
            InlineKeyboardButton("📆 Weekly", callback_data="stats_weekly"),
        ],
        [
            InlineKeyboardButton("🗓️ Monthly", callback_data="stats_monthly"),
            InlineKeyboardButton("📈 Yearly", callback_data="stats_yearly"),
        ],
        [
            InlineKeyboardButton("📊 Overall", callback_data="stats_overall"),
            InlineKeyboardButton("🔀 By Pair", callback_data="stats_pair"),
        ],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def cmd_start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *SELAMAT DATANG DI TRADING ASSISTANT BOT!*\n\n"
        "Saya adalah asisten trading pribadi Anda.\n"
        "Saya otomatis mencatat *Trading Journal* dari postingan channel/chat Anda dan memantau *Economic News* High Impact.\n\n"
        "Pilih menu di bawah ini untuk memulai:"
    )
    await update.effective_message.reply_text(text, reply_markup=build_main_menu_keyboard(), parse_mode="Markdown")


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_main":
        await query.edit_message_text(
            "🏠 *MAIN MENU*\nPilih kategori menu yang ingin Anda akses:",
            reply_markup=build_main_menu_keyboard(),
            parse_mode="Markdown",
        )

    elif data == "menu_journal":
        await query.edit_message_text(
            "📖 *TRADING JOURNAL MENU*\nPilih opsi di bawah ini:",
            reply_markup=build_journal_menu_keyboard(),
            parse_mode="Markdown",
        )

    elif data == "menu_news":
        await query.edit_message_text(
            "📅 *ECONOMIC NEWS MENU*\nPilih opsi di bawah ini:",
            reply_markup=build_news_menu_keyboard(),
            parse_mode="Markdown",
        )

    elif data == "menu_stats":
        await query.edit_message_text(
            "📊 *STATISTICS MENU*\nPilih laporan statistik yang ingin ditampilkan:",
            reply_markup=build_stats_menu_keyboard(),
            parse_mode="Markdown",
        )

    elif data == "menu_settings":
        trades = db.get_all_trades()
        open_trades = [t for t in trades if t.get("status") == "OPEN"]
        text = (
            "⚙️ *BOT STATUS & SETTINGS*\n━━━━━━━━━━━━━━━━━━━\n"
            "🟢 *Status:* `ONLINE` \n"
            f"📊 *Total Trades:* `{len(trades)}` \n"
            f"🔓 *Open Trades:* `{len(open_trades)}` \n"
            f"🕒 *Timezone:* `{cfg.TIMEZONE}` \n"
            f"🚩 *Currencies:* `{', '.join(cfg.WATCHED_CURRENCIES)}` \n"
        )
        reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="menu_main")]])
        await query.edit_message_text(text, reply_markup=reply_kb, parse_mode="Markdown")

    # --- Submenu Callbacks ---

    elif data == "journal_today":
        await stats.today_trades_list(update, context)

    elif data == "journal_open":
        trades = db.get_open_trades()
        if not trades:
            text = "ℹ️ Tidak ada trade yang sedang OPEN."
        else:
            text = "🔓 *OPEN TRADES saat ini:*\n━━━━━━━━━━━━━━━━━━━\n\n"
            for t in trades:
                trade_id = t.get("id")
                code = t.get("trade_code", f"#{trade_id}")
                text += f"• `{code}` | *{t['pair']}* {t['direction']} | Entry: `{t.get('entry_price') or '-'}`\n"
        reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Journal Menu", callback_data="menu_journal")]])
        await query.edit_message_text(text, reply_markup=reply_kb, parse_mode="Markdown")

    elif data == "journal_recent":
        trades = db.get_recent_trades(10)
        if not trades:
            text = "ℹ️ Belum ada trade yang tercatat."
        else:
            text = "📜 *10 TRADES TERAKHIR:*\n━━━━━━━━━━━━━━━━━━━\n\n"
            for t in trades:
                res = t.get("result") or t.get("status")
                r_val = f"{t.get('actual_r'):+}R" if t.get('actual_r') is not None else "OPEN"
                trade_id = t.get("id")
                code = t.get("trade_code", f"#{trade_id}")
                text += f"• `{code}` | *{t['pair']}* {t['direction']} | Result: `{res}` (`{r_val}`)\n"
        reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Journal Menu", callback_data="menu_journal")]])
        await query.edit_message_text(text, reply_markup=reply_kb, parse_mode="Markdown")

    # --- News Menu Callbacks ---
    elif data == "news_today":
        await news_handler.cmd_today(update, context)

    elif data == "news_week":
        await news_handler.cmd_week(update, context)

    elif data == "news_next":
        await news_handler.cmd_next(update, context)

    elif data == "news_refresh":
        await query.edit_message_text("🔄 *Memperbarui cache ForexFactory calendar via Playwright...*", parse_mode="Markdown")
        events = await news_handler.fetch_calendar(cfg, db)
        text = f"✅ Cache diperbarui! `{len(events)}` High Impact events tersimpan."
        reply_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to News Menu", callback_data="menu_news")]])
        await query.edit_message_text(text, reply_markup=reply_kb, parse_mode="Markdown")

    # --- Stats Menu Callbacks ---
    elif data == "stats_daily":
        await stats.daily(update, context)

    elif data == "stats_weekly":
        await stats.weekly(update, context)

    elif data == "stats_monthly":
        await stats.monthly(update, context)

    elif data == "stats_yearly":
        await stats.yearly(update, context)

    elif data == "stats_overall":
        await stats.overall(update, context)

    elif data == "stats_pair":
        await stats.pair_stats(update, context)
