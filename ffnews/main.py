import logging
import asyncio
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from config import cfg
from database import Database
from telegram_handler import cmd_today, cmd_tomorrow, cmd_week, cmd_next, cmd_status
from scheduler import Scheduler
from telegram import Bot

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    if not cfg.BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment")
        return

    db = Database("ffnews.db")
    db.init_db()

    app = ApplicationBuilder().token(cfg.BOT_TOKEN).build()

    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("tomorrow", cmd_tomorrow))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("next", cmd_next))
    app.add_handler(CommandHandler("status", cmd_status))

    # Start scheduler as background task after app starts
    async def _start_scheduler(app):
        bot = app.bot
        # store owner id on bot for sending; assume BOT_OWNER env or use first chat
        bot.owner_id = int(__import__("os").environ.get("BOT_OWNER", "0"))
        sched = Scheduler(bot)
        sched.start()

    app.post_init = _start_scheduler

    logger.info("Starting FF News Bot")
    app.run_polling()


if __name__ == "__main__":
    main()
