import logging
import re
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID, DB_PATH
import database
import profanity

logger = logging.getLogger("BlinModBot")


def is_admin(user_id: int) -> bool:
    """Check if the requesting user is the registered ADMIN_ID."""
    return user_id == ADMIN_ID


async def cmd_addword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /addword <word>"""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ Укажите слово или корень для добавления: `/addword <слово>`", parse_mode="Markdown")
        return

    raw_word = context.args[0].strip()
    norm_word = profanity.normalize_text(raw_word)

    if not norm_word:
        await update.message.reply_text("❌ Неверное слово.")
        return

    added = await database.add_word(DB_PATH, norm_word)
    if added:
        await update.message.reply_text(f"✅ Слово/корень `{norm_word}` успешно добавлено в словарь мата.", parse_mode="Markdown")
        logger.info(f"Admin added word '{norm_word}' to dictionary.")
    else:
        await update.message.reply_text(f"⚠️ Слово/корень `{norm_word}` уже присутствует в словаре.", parse_mode="Markdown")


async def cmd_removeword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /removeword <word>"""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ Укажите слово для удаления: `/removeword <слово>`", parse_mode="Markdown")
        return

    raw_word = context.args[0].strip()
    norm_word = profanity.normalize_text(raw_word)

    removed = await database.remove_word(DB_PATH, norm_word)
    if removed:
        await update.message.reply_text(f"✅ Слово/корень `{norm_word}` удалено из словаря мата.", parse_mode="Markdown")
        logger.info(f"Admin removed word '{norm_word}' from dictionary.")
    else:
        await update.message.reply_text(f"⚠️ Слово/корень `{norm_word}` не найдено в словаре.", parse_mode="Markdown")


async def cmd_wordlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /wordlist (sent ONLY in private message to admin)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    words = await database.get_words(DB_PATH)
    if not words:
        msg_text = "📖 Словарь мата пуст."
    else:
        words_formatted = ", ".join(f"`{w}`" for w in words)
        msg_text = f"📖 **Текущий словарь мата ({len(words)} элементов):**\n\n{words_formatted}"

    try:
        await context.bot.send_message(chat_id=user.id, text=msg_text, parse_mode="Markdown")
        if update.effective_chat.type != "private":
            await update.message.reply_text("📥 Список слов отправлен вам в личные сообщения.")
    except Exception as e:
        logger.error(f"Failed to send /wordlist in PM to admin: {e}")
        await update.message.reply_text("❌ Ошибка отправки в личку. Убедитесь, что вы запустили диалог с ботом (/start в ЛС).")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /unban <user_id | @username>"""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ Укажите ID или @username пользователя: `/unban <ID или @username>`", parse_mode="Markdown")
        return

    target_raw = context.args[0].strip()
    target_id = None

    if target_raw.isdigit():
        target_id = int(target_raw)
    elif target_raw.startswith("@"):
        username = target_raw[1:].lower()
        async with database.aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id FROM violations WHERE LOWER(username) = ?", (f"@{username}",)) as cursor:
                row = await cursor.fetchone()
                if row:
                    target_id = row[0]

    if not target_id:
        await update.message.reply_text(f"❌ Пользователь `{target_raw}` не найден в базе нарушителей.", parse_mode="Markdown")
        return

    await database.unban_user_db(DB_PATH, target_id)
    await database.reset_user_violation(DB_PATH, target_id)

    if update.effective_chat and update.effective_chat.type != "private":
        try:
            await context.bot.unban_chat_member(chat_id=update.effective_chat.id, user_id=target_id)
        except Exception as e:
            logger.warning(f"Could not unban user {target_id} in chat via Telegram API: {e}")

    await update.message.reply_text(f"✅ Пользователь `ID: {target_id}` успешно разбанен и его счётчик нарушений сброшен.", parse_mode="Markdown")
    logger.info(f"Admin unbanned and reset violations for user {target_id}.")


async def cmd_resetstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /resetstats [user_id | @username] (defaults to self if no args)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    target_id = user.id
    target_name = f"ID: {user.id}"

    if context.args:
        target_raw = context.args[0].strip()
        if target_raw.isdigit():
            target_id = int(target_raw)
            target_name = f"ID: {target_id}"
        elif target_raw.startswith("@"):
            username = target_raw[1:].lower()
            async with database.aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT user_id FROM violations WHERE LOWER(username) = ?", (f"@{username}",)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        target_id = row[0]
                        target_name = target_raw

    await database.reset_user_violation(DB_PATH, target_id)
    await update.message.reply_text(f"✅ Счётчик нарушений для пользователя `{target_name}` успешно сброшен в 0.", parse_mode="Markdown")
    logger.info(f"Admin reset violations for {target_name}.")
