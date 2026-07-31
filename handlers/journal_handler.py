import logging
from telegram import Update
from telegram.ext import ContextTypes
from database import Database
from config import Config
from parser import parse_trade_journal, parse_trade_result

logger = logging.getLogger(__name__)

cfg = Config()
db = Database(cfg.DB_PATH, cfg)


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

    # Check if message is sent from channel/chat where BOT_OWNER_ID or TARGET_CHAT_ID is matching
    message = update.effective_message
    if message and message.from_user and str(message.from_user.id) == str(cfg.BOT_OWNER_ID):
        return True

    return False


async def handle_auto_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Auto-detects BEFORE TRADE journal entries or trade result replies.
    Guarded to allow auto-recording and updates only from authorized user/owner.
    """
    message = update.effective_message
    if not message:
        return

    # Owner Security Guard Check
    if not is_owner_or_authorized(update, cfg):
        logger.info(f"Ignored message from unauthorized user ID: {update.effective_user.id if update.effective_user else 'Channel'}")
        return

    text = message.text or message.caption or ""
    chat_id = message.chat_id
    message_id = message.message_id

    # 1. Check if this is a reply or contains a trade_code resolving a trade
    trade = None
    if message.reply_to_message:
        reply_to_id = message.reply_to_message.message_id
        trade = db.get_trade_by_message(chat_id, reply_to_id)

    # Fallback lookup by trade code in message text (e.g. "#TRADE-101 TP +3R")
    if not trade and ("#TRADE-" in text.upper() or "#" in text):
        words = text.split()
        for w in words:
            if w.startswith("#"):
                trade = db.get_trade_by_code(w)
                if trade:
                    break

    if trade:
        result_data = parse_trade_result(text)
        if result_data:
            after_photo_id = None
            if message.photo:
                after_photo_id = message.photo[-1].file_id

            db.update_trade_result(
                trade_id=trade["id"],
                result=result_data["result"],
                actual_r=result_data["actual_r"],
                after_photo_id=after_photo_id,
            )

            trade_id = trade["id"]
            code = trade.get("trade_code", f"#TRADE-{trade_id}")
            reply_text = (
                f"✅ *TRADE RESOLVED & UPDATED!*\n\n"
                f"🏷️ *Trade Code:* `{code}`\n"
                f"📊 *Pair:* `{trade['pair']}` | *Direction:* `{trade['direction']}`\n"
                f"🎯 *Outcome:* `{result_data['result']}`\n"
                f"💰 *Realized R:* `{result_data['actual_r']:+}R`\n"
                f"📅 *Status:* `CLOSED`"
            )
            if after_photo_id:
                reply_text += "\n🖼️ *After-Trade Screenshot attached.*"

            await message.reply_text(reply_text, parse_mode="Markdown")
            return

    # 2. Check if this is a new BEFORE TRADE post
    trade_data = parse_trade_journal(text)
    if trade_data:
        before_photo_id = None
        if message.photo:
            before_photo_id = message.photo[-1].file_id

        trade_data["chat_id"] = chat_id
        trade_data["message_id"] = message_id
        trade_data["before_photo_id"] = before_photo_id

        trade_id = db.create_trade(trade_data)
        trade = db.get_trade_by_id(trade_id)

        response_text = (
            f"📥 *TRADE JOURNAL RECORDED!*\n\n"
            f"🏷️ *Trade Code:* `{trade.get('trade_code')}`\n"
            f"🔀 *Pair:* `{trade['pair']}` | *Direction:* `{trade['direction']}`\n"
            f"📌 *Entry:* `{trade.get('entry_price') or '-'}`\n"
            f"🛑 *SL:* `{trade.get('stop_loss') or '-'}` | *TP:* `{trade.get('take_profit') or '-'}`\n"
            f"⚖️ *Planned RR:* `{trade.get('planned_rr')}R` | *Model:* `{trade.get('model')}`\n"
            f"📅 *Status:* `OPEN`\n\n"
            f"💡 *Reply to this post with 'TP +3R', 'SL -1R', or 'BE' when trade finishes!*"
        )

        sent_msg = await message.reply_text(response_text, parse_mode="Markdown")

        # Update bot_reply_message_id and message mapping without closing the trade!
        with db.conn() as c:
            c.execute(
                "UPDATE trades SET bot_reply_message_id=? WHERE id=?",
                (sent_msg.message_id, trade_id),
            )
            c.execute(
                "INSERT OR REPLACE INTO message_mappings (chat_id, message_id, trade_id) VALUES (?,?,?)",
                (chat_id, sent_msg.message_id, trade_id),
            )


async def handle_edited_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles edited messages: if an open journal entry post is edited, update journal data.
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
                        risk_input=?, planned_rr=?, model=?, notes=?
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
                        trade["id"],
                    ),
                )
            logger.info(f"Trade {trade['id']} updated via edited message.")
