import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from telegram import Update
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import BOT_TOKEN, ADMIN_ID, DB_PATH, logger
import database
import profanity
from handlers import admin, user, messages

# Ensure DB path is absolute
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(BASE_DIR, DB_PATH)

app = Flask(__name__)

# Configure HTTPXRequest with robust timeouts
request_config = HTTPXRequest(
    connection_pool_size=16,
    connect_timeout=15.0,
    read_timeout=15.0,
    write_timeout=15.0,
    pool_timeout=10.0,
    http_version="1.1",
)

# Build Telegram Application instance
ptb_app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .request(request_config)
    .build()
)

# Register Handlers
ptb_app.add_handler(CommandHandler("start", user.cmd_start))
ptb_app.add_handler(CommandHandler("help", user.cmd_help))
ptb_app.add_handler(CommandHandler("mystats", user.cmd_mystats))
ptb_app.add_handler(CommandHandler("addword", admin.cmd_addword))
ptb_app.add_handler(CommandHandler("removeword", admin.cmd_removeword))
ptb_app.add_handler(CommandHandler("wordlist", admin.cmd_wordlist))
ptb_app.add_handler(CommandHandler("unban", admin.cmd_unban))
ptb_app.add_handler(CommandHandler("resetstats", admin.cmd_resetstats))

group_filter = (filters.TEXT & ~filters.COMMAND)
ptb_app.add_handler(MessageHandler(group_filter, messages.handle_group_message))
ptb_app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & group_filter, messages.handle_group_message))

_initialized = False
_last_cleanup = 0

async def init_ptb():
    """Initializes the database, cache and PTB bot on first request."""
    global _initialized
    if not _initialized:
        logger.info("Initializing database for Webhook...")
        await database.init_db(DB_PATH)
        words = await database.get_words(DB_PATH)
        profanity.set_cached_words(words)
        await ptb_app.initialize()
        await ptb_app.start()
        _initialized = True
        logger.info("BlinModBot Webhook application ready.")

async def maybe_cleanup():
    """Runs ban and violation cleanup once an hour when traffic passes through."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup > 3600:
        _last_cleanup = now
        try:
            # Check expired bans
            expired = await database.get_expired_bans(DB_PATH)
            for item in expired:
                uid = item["user_id"]
                cid = item.get("chat_id")
                if cid:
                    try:
                        await ptb_app.bot.unban_chat_member(chat_id=cid, user_id=uid)
                    except Exception:
                        pass
                await database.unban_user_db(DB_PATH, uid)
            # Reset inactive violators
            inactive = await database.get_inactive_violators(DB_PATH, days=30)
            for item in inactive:
                await database.reset_user_violation(DB_PATH, item["user_id"])
        except Exception as e:
            logger.error("Periodic cleanup error in webhook: %s", e)

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "online",
        "bot": "BlinModBot",
        "mode": "webhook",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    if not request.is_json:
        return "Invalid request", 400

    update_data = request.get_json()

    async def handle_update():
        await init_ptb()
        await maybe_cleanup()
        update = Update.de_json(update_data, ptb_app.bot)
        await ptb_app.process_update(update)

    try:
        asyncio.run(handle_update())
    except Exception as e:
        logger.error("Error processing update via webhook: %s", e)
        return "Internal Error", 500

    return "OK", 200

@app.route("/set_webhook", methods=["GET"])
def set_webhook_route():
    webhook_url = f"https://{request.host}/webhook"
    async def call_set():
        await ptb_app.initialize()
        return await ptb_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False
        )
    success = asyncio.run(call_set())
    return jsonify({"webhook_set": success, "url": webhook_url})

if __name__ == "__main__":
    app.run(port=5000)