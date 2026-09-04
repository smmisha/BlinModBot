import logging
from telegram.ext import ContextTypes
from config import DB_PATH
import database

logger = logging.getLogger("BlinModBot")


async def job_check_expired_bans(context: ContextTypes.DEFAULT_TYPE):
    """
    Background job that runs periodically to clear expired 30-day bans in database
    and ensure users are unbanned in Telegram.
    """
    try:
        expired_users = await database.get_expired_bans(DB_PATH)
        if not expired_users:
            return

        logger.info(f"Background check: found {len(expired_users)} expired bans to process.")

        for user in expired_users:
            user_id = user["user_id"]
            chat_id = user.get("chat_id")
            username = user.get("username", str(user_id))

            # Unban user in Telegram group if chat_id is known
            if chat_id:
                try:
                    await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
                    logger.info(f"Unbanned user {username} (ID: {user_id}) in Telegram chat {chat_id}.")
                except Exception as e:
                    logger.warning(f"Failed to unban user {user_id} in Telegram chat {chat_id}: {e}")

            # Clear banned_until in DB
            await database.unban_user_db(DB_PATH, user_id)
            logger.info(f"Auto-unbanned user {username} (ID: {user_id}) after 30-day period expired.")
    except Exception as e:
        logger.error(f"Error in background job job_check_expired_bans: {e}", exc_info=True)


async def job_reset_inactive_violations(context: ContextTypes.DEFAULT_TYPE):
    """
    Background job that resets violation_count to 0 for users who haven't violated in 30+ days.
    """
    try:
        inactive_users = await database.get_inactive_violators(DB_PATH, days=30)
        if not inactive_users:
            return

        logger.info(f"Background check: resetting violation count for {len(inactive_users)} users inactive for 30+ days.")

        for user in inactive_users:
            user_id = user["user_id"]
            username = user.get("username", str(user_id))

            await database.reset_user_violation(DB_PATH, user_id)
            logger.info(f"Reset violation counter to 0 for user {username} (ID: {user_id}) after 30 clean days.")
    except Exception as e:
        logger.error(f"Error in background job job_reset_inactive_violations: {e}", exc_info=True)
