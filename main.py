import logging.config
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import LOGGING_CONFIG, Config
from database import Database
from scheduler import NewsScheduler
from handlers.journal_handler import handle_auto_journal, handle_edited_journal
from handlers import news_handler, stats
from handlers.menu_handler import cmd_start_menu, handle_menu_callback

load_dotenv()

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs exceptions raised during update handling."""
    logger.error("Exception handling update:", exc_info=context.error)


def main() -> None:
    cfg = Config()
    if not cfg.BOT_TOKEN:
        logger.error("BOT_TOKEN is missing in environment variables (.env). Exiting.")
        return

    db = Database(cfg.DB_PATH, cfg)
    db.init_db()

    scheduler = NewsScheduler(None, cfg, db)

    async def post_init(application) -> None:
        scheduler.app = application
        scheduler.start()
        logger.info("APScheduler started post-init.")

    app = ApplicationBuilder().token(cfg.BOT_TOKEN).post_init(post_init).build()

    # Global Error Handler
    app.add_error_handler(error_handler)

    # Slash Commands
    app.add_handler(CommandHandler("start", cmd_start_menu))
    app.add_handler(CommandHandler("help", cmd_start_menu))

    # News Slash Commands
    app.add_handler(CommandHandler("today", news_handler.cmd_today))
    app.add_handler(CommandHandler("week", news_handler.cmd_week))
    app.add_handler(CommandHandler("next", news_handler.cmd_next))
    app.add_handler(CommandHandler("status", news_handler.cmd_status))

    # Statistics Slash Commands
    app.add_handler(CommandHandler("daily", stats.daily))
    app.add_handler(CommandHandler("weekly", stats.weekly))
    app.add_handler(CommandHandler("monthly", stats.monthly))
    app.add_handler(CommandHandler("yearly", stats.yearly))
    app.add_handler(CommandHandler("overall", stats.overall))
    app.add_handler(CommandHandler("pair", stats.pair_stats))
    app.add_handler(CommandHandler("weekday", stats.weekday_stats))
    app.add_handler(CommandHandler("month", stats.month_stats))
    app.add_handler(CommandHandler("delete", stats.delete_trade))

    # Menu Callback Query Handler
    app.add_handler(CallbackQueryHandler(handle_menu_callback))

    # Edited Post/Message Handler
    app.add_handler(
        MessageHandler(
            (filters.UpdateType.EDITED_MESSAGE | filters.UpdateType.EDITED_CHANNEL_POST),
            handle_edited_journal,
        )
    )

    # Auto-detection Message Handler (Captures text or photo posts & replies)
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            handle_auto_journal,
        )
    )

    logger.info("Trading Assistant Telegram Bot successfully started and listening...")
    try:
        app.run_polling()
    finally:
        scheduler.stop()


if __name__ == "__main__":
    main()
