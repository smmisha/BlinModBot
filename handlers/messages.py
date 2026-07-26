import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import DB_PATH, ADMIN_ID
import database
import profanity
import moderation

logger = logging.getLogger("BlinModBot")


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Listens to text messages in groups / supergroups (both new messages and edited messages).
    Checks text for profanity and invokes the moderation engine if profanity is detected.
    """
    message = update.effective_message
    if not message or not message.text:
        return

    # Only process in group/supergroup or private test chats
    if update.effective_chat and update.effective_chat.type == "private":
        # In private chat, we don't apply moderation penalties, only commands work
        return

    user = message.from_user
    if not user or user.is_bot:
        return

    raw_text = message.text

    # Reply protection check:
    # If the message is a reply to a warning from this bot and does NOT contain profanity,
    # it is considered a clean correction and no violation is triggered.
    profanity_words = await database.get_words(DB_PATH)
    is_profane, matched_word = profanity.contains_profanity(raw_text, profanity_words)

    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == context.bot.id:
            if not is_profane:
                # User replied to bot warning cleanly -> acknowledge/ignore
                logger.info(f"User {user.id} replied cleanly to bot warning. No violation added.")
                return

    if is_profane and matched_word:
        logger.warning(f"Profanity detected in chat {update.effective_chat.id} from user {user.id} ({user.full_name}): matched stem '{matched_word}'")
        await moderation.process_violation(update, context, matched_word)
