import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler
from config import LOGGING_CONFIG, Config
from database import Database
from handlers import journal, stats

load_dotenv()

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


def main() -> None:
    cfg = Config()
    db = Database("database.db", cfg)
    db.init_db()

    app = ApplicationBuilder().token(cfg.BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", journal.start))
    app.add_handler(journal.conv_handler)

    # Stats and utility commands
    app.add_handler(CommandHandler("weekly", stats.weekly))
    app.add_handler(CommandHandler("monthly", stats.monthly))
    app.add_handler(CommandHandler("pair", stats.pair_stats))
    app.add_handler(CommandHandler("model", stats.model_stats))
    app.add_handler(CommandHandler("today", stats.today))
    app.add_handler(CommandHandler("delete", stats.delete_trade))
    app.add_handler(CommandHandler("edit", journal.edit_conv))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
