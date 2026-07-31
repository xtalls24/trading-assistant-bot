import asyncio
import logging
from typing import Dict, Any
from telegram import Update
from telegram.ext import ContextTypes
from database import Database
from config import Config
from parser import parse_trade_journal, parse_trade_result

logger = logging.getLogger(__name__)

cfg = Config()
db = Database(cfg.DB_PATH, cfg)

# Media Group Buffer (combines multi-photo album updates into a single trade entry)
MEDIA_GROUP_CACHE: Dict[str, Dict[str, Any]] = {}
MEDIA_GROUP_LOCK = asyncio.Lock()


def is_owner_or_authorized(update: Update, cfg: Config) -> bool:
    """
    Checks if the message sender or channel post author is authorized.
    If BOT_OWNER_ID is set, verifies that user.id matches BOT_OWNER_ID.
    """
    if not cfg.BOT_OWNER_ID:
        return True

    user = update.effective_user
    if user and str(user.id) == str(cfg.BOT_OWNER_ID):
        return True

    message = update.effective_message
    if message and message.from_user and str(message.from_user.id) == str(cfg.BOT_OWNER_ID):
        return True

    return False


async def handle_auto_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Silently records trade journal entries published in the channel.
    Supports single messages and multi-photo media groups (album with before/after screenshots).
    NO reply/confirmation messages are sent to Telegram.
    """
    message = update.effective_message
    if not message:
        return

    if not is_owner_or_authorized(update, cfg):
        logger.info(
            f"Ignored message from unauthorized user ID: {update.effective_user.id if update.effective_user else 'Channel'}"
        )
        return

    text = message.text or message.caption or ""
    chat_id = message.chat_id
    message_id = message.message_id
    photo_id = message.photo[-1].file_id if message.photo else None

    # Handle Media Groups (Albums with 2 screenshots: Before & After)
    if message.media_group_id:
        group_id = message.media_group_id
        async with MEDIA_GROUP_LOCK:
            if group_id not in MEDIA_GROUP_CACHE:
                MEDIA_GROUP_CACHE[group_id] = {
                    "chat_id": chat_id,
                    "message_ids": [message_id],
                    "text": text,
                    "photos": [photo_id] if photo_id else [],
                    "processed": False,
                }
                # Schedule processing window for media group updates (~1.2 sec)
                asyncio.create_task(_process_media_group_after_delay(group_id))
            else:
                entry = MEDIA_GROUP_CACHE[group_id]
                entry["message_ids"].append(message_id)
                if photo_id and photo_id not in entry["photos"]:
                    entry["photos"].append(photo_id)
                if text and not entry["text"]:
                    entry["text"] = text
        return

    # Handle Single Message Entry (Text or Single Photo)
    await _save_journal_entry(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        photos=[photo_id] if photo_id else [],
    )


async def _process_media_group_after_delay(group_id: str):
    """Wait for all items of a media group album to arrive, then save silently."""
    await asyncio.sleep(1.2)
    async with MEDIA_GROUP_LOCK:
        entry = MEDIA_GROUP_CACHE.pop(group_id, None)

    if entry and not entry.get("processed"):
        await _save_journal_entry(
            chat_id=entry["chat_id"],
            message_id=entry["message_ids"][0],
            text=entry["text"],
            photos=entry["photos"],
        )


async def _save_journal_entry(chat_id: int, message_id: int, text: str, photos: list):
    """
    Parses trade information and saves directly to SQLite without sending any reply.
    """
    trade_data = parse_trade_journal(text)
    if not trade_data:
        # Fallback check: reply or trade result update if applicable
        result_data = parse_trade_result(text)
        if result_data:
            existing_trade = db.get_trade_by_message(chat_id, message_id)
            if existing_trade:
                after_photo = photos[0] if photos else None
                db.update_trade_result(
                    trade_id=existing_trade["id"],
                    result=result_data["result"],
                    actual_r=result_data["actual_r"],
                    after_photo_id=after_photo,
                )
                logger.info(f"Silently updated trade #{existing_trade['id']} via result reply.")
        return

    before_photo_id = photos[0] if len(photos) >= 1 else None
    after_photo_id = photos[1] if len(photos) >= 2 else None

    trade_data["chat_id"] = chat_id
    trade_data["message_id"] = message_id
    trade_data["before_photo_id"] = before_photo_id

    # Create trade in database
    trade_id = db.create_trade(trade_data)

    # If completed trade, update result and after_photo_id in SQLite
    if trade_data.get("status") == "CLOSED" or trade_data.get("result"):
        db.update_trade_result(
            trade_id=trade_id,
            result=trade_data.get("result") or "BE",
            actual_r=trade_data.get("actual_r") or 0.0,
            after_photo_id=after_photo_id,
        )

    logger.info(f"Silently recorded trade ID #{trade_id} ({trade_data['pair']} {trade_data['direction']}). No reply sent.")


async def handle_edited_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles edited messages silently: updates SQLite record if journal entry post is edited.
    No reply messages sent.
    """
    message = update.edited_message or update.edited_channel_post
    if not message or not is_owner_or_authorized(update, cfg):
        return

    chat_id = message.chat_id
    message_id = message.message_id
    text = message.text or message.caption or ""

    trade = db.get_trade_by_message(chat_id, message_id)
    if trade:
        trade_data = parse_trade_journal(text)
        if trade_data:
            with db.conn() as c:
                c.execute(
                    """
                    UPDATE trades
                    SET pair=?, direction=?, entry_price=?, stop_loss=?, take_profit=?,
                        risk_input=?, planned_rr=?, model=?, notes=?, status=?, result=?, actual_r=?
                    WHERE id=?
                    """,
                    (
                        trade_data["pair"],
                        trade_data["direction"],
                        trade_data.get("entry_price"),
                        trade_data.get("stop_loss"),
                        trade_data.get("take_profit"),
                        trade_data.get("risk_input"),
                        trade_data.get("planned_rr"),
                        trade_data.get("model"),
                        trade_data.get("notes"),
                        trade_data.get("status", "CLOSED"),
                        trade_data.get("result"),
                        trade_data.get("actual_r"),
                        trade["id"],
                    ),
                )
            logger.info(f"Silently updated trade #{trade['id']} via edited channel post.")
