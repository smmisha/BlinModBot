import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.error import TelegramError, Forbidden, BadRequest

from config import ADMIN_ID, DB_PATH
import database

logger = logging.getLogger("BlinModBot")


async def notify_admin_missing_rights(context: ContextTypes.DEFAULT_TYPE, action: str, chat_title: str):
    """Sends a private message to ADMIN_ID if the bot lacks required admin permissions."""
    if not ADMIN_ID:
        return
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🚨 **Ошибка прав бота!**\n\n"
                f"Бот не смог выполнить действие `{action}` в чате «{chat_title}».\n"
                f"Пожалуйста, убедитесь, что бот добавлен в админы группы и имеет права на:\n"
                f"- Удаление сообщений (Delete messages)\n"
                f"- Блокировку участников (Ban users)"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send admin notification to {ADMIN_ID}: {e}")


async def process_violation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    matched_word: str
):
    """
    Handles a detected profanity violation according to the escalation ladder:
    1: Warning in chat
    2: Delete message + Warning in chat
    3: Delete message + Kick from group
    4: Delete message + 30-day Ban
    """
    message: Message = update.effective_message
    if not message or not message.from_user:
        return

    user = message.from_user
    chat = update.effective_chat
    user_id = user.id
    username = f"@{user.username}" if user.username else user.full_name
    chat_title = chat.title if chat else "Чат"

    # Record violation in DB
    new_count = await database.record_violation(DB_PATH, user_id, username)
    logger.info(f"User {username} (ID: {user_id}) violation count: {new_count}. Matched: {matched_word}")

    user_mention = f"[{user.full_name}](tg://user?id={user_id})"

    # --- LADDER STEP 1: WARNING ---
    if new_count == 1:
        text = (
            f"⚠️ {user_mention}, пожалуйста, воздержитесь от использования мата в чате поддержки.\n"
            f"Удалите сообщение или замените матерные слова на нейтральные (например, «блин»).\n\n"
            f"📌 *Это ваше 1-е нарушение.* (После 4-го нарушения следует бан на 30 дней)."
        )
        await message.reply_text(text, parse_mode="Markdown")

    # --- LADDER STEP 2: DELETE MESSAGE ---
    elif new_count == 2:
        # Try deleting message
        try:
            await message.delete()
        except (Forbidden, BadRequest) as e:
            logger.warning(f"Could not delete message for step 2: {e}")
            await notify_admin_missing_rights(context, "удаление сообщения", chat_title)

        text = (
            f"⚠️ {user_mention}, ваше сообщение было удалено за использование мата.\n\n"
            f"📌 *Это ваше 2-е нарушение.* Повторное нарушение приведёт к временному исключению из группы."
        )
        await context.bot.send_message(chat_id=chat.id, text=text, parse_mode="Markdown")

    # --- LADDER STEP 3: KICK FROM GROUP ---
    elif new_count == 3:
        # Try deleting message
        try:
            await message.delete()
        except (Forbidden, BadRequest) as e:
            logger.warning(f"Could not delete message for step 3: {e}")
            await notify_admin_missing_rights(context, "удаление сообщения", chat_title)

        # Kick = ban then unban immediately so user can rejoin via invite link
        kicked = False
        try:
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=user_id)
            await context.bot.unban_chat_member(chat_id=chat.id, user_id=user_id)
            kicked = True
        except (Forbidden, BadRequest) as e:
            logger.error(f"Could not kick user {user_id}: {e}")
            await notify_admin_missing_rights(context, "исключение участника (кик)", chat_title)

        if kicked:
            text = (
                f"🚫 {user_mention} был исключён из группы за 3-е нарушение правил общения.\n"
                f"Пользователь может вернуться по ссылке в группу, но следующее нарушение приведёт к бану на 30 дней."
            )
        else:
            text = (
                f"⚠️ {user_mention}, вы совершили 3-е нарушение правил!\n"
                f"Следующее нарушение приведёт к бану на 30 дней."
            )

        await context.bot.send_message(chat_id=chat.id, text=text, parse_mode="Markdown")

    # --- LADDER STEP 4+: 30-DAY BAN ---
    else:
        # Try deleting message
        try:
            await message.delete()
        except (Forbidden, BadRequest) as e:
            logger.warning(f"Could not delete message for step 4: {e}")
            await notify_admin_missing_rights(context, "удаление сообщения", chat_title)

        until_date = datetime.now(timezone.utc) + timedelta(days=30)
        await database.set_banned_until(DB_PATH, user_id, until_date)

        banned = False
        try:
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=user_id, until_date=until_date)
            banned = True
        except (Forbidden, BadRequest) as e:
            logger.error(f"Could not ban user {user_id}: {e}")
            await notify_admin_missing_rights(context, "бан на 30 дней", chat_title)

        if banned:
            text = f"⛔ {user_mention} забанен на 30 дней за 4-е нарушение правил общения."
        else:
            text = f"⛔ {user_mention} достиг 4-го нарушения правил общения (требуется бан на 30 дней)."

        await context.bot.send_message(chat_id=chat.id, text=text, parse_mode="Markdown")
