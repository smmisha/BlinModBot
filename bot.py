import asyncio
import os
import sys
import logging

from config import BOT_TOKEN, ADMIN_ID, DB_PATH, logger

from telegram import Update
from telegram.error import Conflict
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import database
import profanity
from background import job_check_expired_bans, job_reset_inactive_violations
from handlers import admin, user, messages


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler. Logs errors and exits on Conflict to allow supervisor restart."""
    err = context.error
    if isinstance(err, Conflict):
        logger.critical("Fatal Conflict detected! Terminating process so supervisor can cleanly restart.")
        sys.exit(1)

    err_str = str(err)
    if "503" in err_str or "ProxyError" in err_str:
        logger.warning("Transient PythonAnywhere proxy error: %s", err)
    else:
        logger.error("Exception in update processing: %s", err)


async def post_init(application):
    """Callback run after application initialization to test DB and setup background jobs."""
    logger.info("Initializing database connection...")
    db_ok = await database.init_db(DB_PATH)
    if not db_ok:
        logger.critical("FATAL: Database connection failed during startup! Shutting down bot.")
        sys.exit(1)

    logger.info("Database initialized successfully.")

    # Load profanity dictionary into memory cache
    words = await database.get_words(DB_PATH)
    profanity.set_cached_words(words)
    logger.info(f"Loaded {len(words)} profanity words into in-memory cache.")

    if application.job_queue:
        application.job_queue.run_repeating(
            job_check_expired_bans,
            interval=3600,
            first=10,
            name="job_check_expired_bans"
        )
        application.job_queue.run_repeating(
            job_reset_inactive_violations,
            interval=86400,
            first=30,
            name="job_reset_inactive_violations"
        )
        logger.info("Background job queue configured successfully.")
    else:
        logger.warning("JobQueue is not enabled! Install python-telegram-bot[job-queue].")

    # Optional HTTP health check server for cloud platforms (e.g. Render Web Service, Railway)
    port_env = os.getenv("PORT")
    if port_env and port_env.isdigit():
        port = int(port_env)
        async def handle_health_check(reader, writer):
            try:
                await reader.read(1024)
                response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"
                writer.write(response)
                await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

        try:
            await asyncio.start_server(handle_health_check, "0.0.0.0", port)
            logger.info(f"Health check HTTP server started on 0.0.0.0:{port}")
        except Exception as e:
            logger.warning(f"Could not start health check HTTP server on port {port}: {e}")



def main():
    """Main entry point for starting the Telegram bot."""
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is empty! Please set BOT_TOKEN in .env or environment variables.")
        sys.exit(1)

    logger.info(f"Starting BlinModBot... Admin ID configured: {ADMIN_ID}")

    request_config = HTTPXRequest(
        connection_pool_size=16,
        connect_timeout=15.0,
        read_timeout=15.0,
        write_timeout=15.0,
        pool_timeout=10.0,
        http_version="1.1",
    )

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request_config)
        .post_init(post_init)
        .build()
    )

    # User Commands
    app.add_handler(CommandHandler("start", user.cmd_start))
    app.add_handler(CommandHandler("help", user.cmd_help))
    app.add_handler(CommandHandler("mystats", user.cmd_mystats))

    # Admin Commands
    app.add_handler(CommandHandler("addword", admin.cmd_addword))
    app.add_handler(CommandHandler("removeword", admin.cmd_removeword))
    app.add_handler(CommandHandler("wordlist", admin.cmd_wordlist))
    app.add_handler(CommandHandler("unban", admin.cmd_unban))
    app.add_handler(CommandHandler("resetstats", admin.cmd_resetstats))

    # Group Messages Handler (both new text messages and edited messages)
    group_filter = (filters.TEXT & ~filters.COMMAND)
    app.add_handler(MessageHandler(group_filter, messages.handle_group_message))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & group_filter, messages.handle_group_message))

    # Global Error Handler
    app.add_error_handler(error_handler)

    logger.info("Bot handlers registered. Starting long polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
