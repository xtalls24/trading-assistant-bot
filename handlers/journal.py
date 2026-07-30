import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from database import Database
from config import Config
from datetime import datetime, date

logger = logging.getLogger(__name__)

cfg = Config()
db = Database("database.db", cfg)


# Conversation states
(DATE, PAIR, DIRECTION, MODEL, BIAS, POI, CONFIRMATION, KILLZONE, RESULT, SAVE) = range(10)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Gunakan /add untuk menambahkan trade jurnal.")


async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tanggal (YYYY-MM-DD):")
    return DATE


async def date_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        # validate
        dt = datetime.fromisoformat(text).date()
        context.user_data["trade"] = {"date": dt.isoformat()}
        await update.message.reply_text("Pair (contoh: EURUSD):")
        return PAIR
    except Exception:
        await update.message.reply_text("Format tanggal salah. Gunakan YYYY-MM-DD.")
        return DATE


async def pair_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["trade"]["pair"] = update.message.text.strip().upper()
    await update.message.reply_text("Direction (BUY/SELL):")
    return DIRECTION


async def direction_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["trade"]["direction"] = update.message.text.strip().upper()
    await update.message.reply_text("Model (C1/C2/C3):")
    return MODEL


async def model_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["trade"]["model"] = update.message.text.strip().upper()
    await update.message.reply_text("Bias:")
    return BIAS


async def bias_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["trade"]["bias"] = update.message.text.strip()
    await update.message.reply_text("POI:")
    return POI


async def poi_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["trade"]["poi"] = update.message.text.strip()
    await update.message.reply_text("Confirmation:")
    return CONFIRMATION


async def confirmation_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["trade"]["confirmation"] = update.message.text.strip()
    await update.message.reply_text("Killzone:")
    return KILLZONE


async def killzone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["trade"]["killzone"] = update.message.text.strip()
    await update.message.reply_text("Result (TP/SL):")
    return RESULT


async def result_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = update.message.text.strip().upper()
    rr = 0.0
    if res == "TP":
        rr = 2.0
    elif res == "SL":
        rr = -1.0
    else:
        await update.message.reply_text("Result harus TP atau SL")
        return RESULT

    context.user_data["trade"]["result"] = res
    context.user_data["trade"]["rr"] = rr

    trade = context.user_data["trade"]
    text = (
        "✅ Trade berhasil disimpan\n\n"
        f"Tanggal : {trade['date']}\n"
        f"Pair : {trade['pair']}\n"
        f"Direction : {trade['direction']}\n"
        f"Model : {trade['model']}\n"
        f"Bias : {trade['bias']}\n"
        f"POI : {trade['poi']}\n"
        f"Confirmation : {trade['confirmation']}\n"
        f"Killzone : {trade['killzone']}\n"
        f"Result : {trade['result']}\n"
        f"RR : {trade['rr']}\n"
    )

    # persist
    db.add_trade(trade)

    await update.message.reply_text(text)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Input dibatalkan.")
    return ConversationHandler.END


def _conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("add", ask_date)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_received)],
            PAIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, pair_received)],
            DIRECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, direction_received)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_received)],
            BIAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, bias_received)],
            POI: [MessageHandler(filters.TEXT & ~filters.COMMAND, poi_received)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmation_received)],
            KILLZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, killzone_received)],
            RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, result_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


conv_handler = _conv_handler()


# Simple edit conversation (asks for ID then reuse fields)
async def edit_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If user provided id as arg
    args = context.args or []
    if args:
        try:
            tid = int(args[0])
        except Exception:
            await update.message.reply_text("ID tidak valid")
            return
    else:
        await update.message.reply_text("Kirim /edit <id>")
        return

    trade = db.get_trade(tid)
    if not trade:
        await update.message.reply_text("Trade tidak ditemukan")
        return

    # Start by showing current trade and ask which field to edit
    text = "Trade ditemukan:\n"
    for k, v in trade.items():
        text += f"{k}: {v}\n"
    text += "\nKirim field yang ingin diubah (contoh: result) diikuti dengan nilai baru, mis: result TP"
    await update.message.reply_text(text)

    return
