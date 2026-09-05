import html
import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes

from config import DB_PATH
import database

logger = logging.getLogger("BlinModBot")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    user = update.effective_user
    username = f"@{user.username}" if user and user.username else f"id:{user.id if user else 'unknown'}"
    logger.info(f"Received /start from {username}")
    first_name = html.escape(user.first_name) if user and user.first_name else "пользователь"
    text = (
        f"Привет, {first_name}! 👋\n\n"
        f"Я бот автоматической модерации правил общения в чате поддержки.\n\n"
        f"📌 <b>Доступные команды в личных сообщениях:</b>\n"
        f"• <code>/mystats</code> — посмотреть вашу статистику нарушений и дату сброса счётчика.\n"
        f"• <code>/help</code> — информация о правилах и поддержке."
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help command."""
    user = update.effective_user
    username = f"@{user.username}" if user and user.username else f"id:{user.id if user else 'unknown'}"
    logger.info(f"Received /help from {username}")
    text = (
        "ℹ️ <b>Правила модерации мата в чате поддержки:</b>\n\n"
        "Для сохранения безопасной и корректной атмосферы в чате действует лестница предупреждений за мат:\n"
        "1️⃣ <b>1-е нарушение</b> — Предупреждение в чате с просьбой удалить или заменить слово.\n"
        "2️⃣ <b>2-е нарушение</b> — Удаление матерного сообщения ботом.\n"
        "3️⃣ <b>3-е нарушение</b> — Временное исключение из группы (кик).\n"
        "4️⃣ <b>4-е нарушение</b> — Бан в группе на 30 дней.\n\n"
        "🔄 <i>Сброс счётчика:</i> Счётчик нарушений обнуляется автоматической системой, если вы не нарушали правила <b>30 дней подряд</b>."
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /mystats command.
    Shows user their violation count, last violation timestamp, and days left until reset.
    Works best in PM to avoid cluttering group chat.
    """
    user = update.effective_user
    if not user:
        return

    username = f"@{user.username}" if user.username else f"id:{user.id}"
    logger.info(f"Received /mystats from {username}")

    # Check if executed in private chat vs group chat
    if update.effective_chat and update.effective_chat.type != "private":
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="📊 Запрос вашей статистики выполнен. Ваша информация показана ниже."
            )
            await update.message.reply_text("📥 Статистика нарушений отправлена вам в личные сообщения.")
        except Exception:
            pass  # Fallback to answering in current chat if PM fails

    viol_data = await database.get_user_violation(DB_PATH, user.id)

    if not viol_data or viol_data.get("violation_count", 0) == 0:
        text = "✅ <b>Ваша статистика чистоты:</b>\nУ вас <b>0</b> нарушений правил общения. Спасибо за соблюдение правил!"
    else:
        count = viol_data["violation_count"]
        last_violation_str = viol_data.get("last_violation_at")
        days_left = 30

        if last_violation_str:
            try:
                last_dt = datetime.fromisoformat(last_violation_str)
                now_dt = datetime.now(timezone.utc)
                elapsed_days = (now_dt - last_dt).days
                days_left = max(0, 30 - elapsed_days)
                formatted_date = last_dt.strftime("%d.%m.%Y %H:%M UTC")
            except Exception:
                formatted_date = html.escape(last_violation_str)
        else:
            formatted_date = "неизвестно"

        banned_until_str = viol_data.get("banned_until")
        ban_info = ""
        if banned_until_str:
            try:
                ban_dt = datetime.fromisoformat(banned_until_str)
                ban_info = f"\n⛔ <b>Текущий бан до:</b> <code>{ban_dt.strftime('%d.%m.%Y %H:%M UTC')}</code>"
            except Exception:
                pass

        text = (
            f"📊 <b>Ваша статистика нарушений:</b>\n\n"
            f"• Текущее количество нарушений: <b>{count} / 4</b>\n"
            f"• Дата последнего нарушения: <code>{formatted_date}</code>\n"
            f"• Дней до автосброса счётчика (при вежливом общении): <b>{days_left} дн.</b>"
            f"{ban_info}"
        )

    # Deliver response
    target_chat_id = user.id if update.effective_chat.type != "private" else update.effective_chat.id
    try:
        await context.bot.send_message(chat_id=target_chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending /mystats: {e}")
        await update.message.reply_text(text, parse_mode="HTML")
