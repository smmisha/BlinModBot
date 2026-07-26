import asyncio
import sys
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import BOT_TOKEN, ADMIN_ID, DB_PATH, logger
import database
from background import job_check_expired_bans, job_reset_inactive_violations
from handlers import admin, user, messages


async def post_init(application):
    """Callback run after application initialization to test DB and setup background jobs."""
    logger.info("Initializing database connection...")
    db_ok = await database.init_db(DB_PATH)
    if not db_ok:
        logger.critical("FATAL: Database connection failed during startup! Shutting down bot.")
        sys.exit(1)

    logger.info("Database initialized successfully.")

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


def main():
    """Main entry point for starting the Telegram bot."""
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is empty! Please set BOT_TOKEN in .env or environment variables.")
        sys.exit(1)

    logger.info(f"Starting BlinModBot... Admin ID configured: {ADMIN_ID}")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

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

    logger.info("Bot handlers registered. Starting long polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
