import logging
import logging.config

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler

from config import LOGGING_CONFIG, Config
from database import Database
from scheduler import Scheduler
from handlers import journal, stats, calendar

load_dotenv()

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = Config()
    if not cfg.BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment")
        return

    db = Database("database.db", cfg)
    db.init_db()

    app = ApplicationBuilder().token(cfg.BOT_TOKEN).build()

    # Journal commands
    app.add_handler(CommandHandler("start", journal.start))
    app.add_handler(journal.conv_handler)
    app.add_handler(CommandHandler("edit", journal.edit_conv))

    # Stats commands
    app.add_handler(CommandHandler("weekly", stats.weekly))
    app.add_handler(CommandHandler("monthly", stats.monthly))
    app.add_handler(CommandHandler("pair", stats.pair_stats))
    app.add_handler(CommandHandler("model", stats.model_stats))
    app.add_handler(CommandHandler("delete", stats.delete_trade))
    app.add_handler(CommandHandler("todaytrades", stats.trades_today))

    # Forex Factory calendar commands (note: "today" here refers to the
    # calendar, distinct from the old journal "today" trade-list command,
    # which is now only reachable via /pair, /model, /weekly, /monthly).
    app.add_handler(CommandHandler("today", calendar.cmd_today))
    app.add_handler(CommandHandler("next", calendar.cmd_next))
    app.add_handler(CommandHandler("status", calendar.cmd_status))

    # Start the calendar alert scheduler as a background asyncio task once
    # the bot's event loop is running, so it never blocks polling.
    async def _on_startup(app):
        scheduler = Scheduler(app.bot, db, cfg)
        scheduler.start()

    app.post_init = _on_startup

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
