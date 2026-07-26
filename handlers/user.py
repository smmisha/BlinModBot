import logging
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from telegram import Update
from telegram.ext import ContextTypes

from config import DB_PATH
import database

logger = logging.getLogger("BlinModBot")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    user = update.effective_user
    text = (
        f"Привет, {user.first_name}! 👋\n\n"
        f"Я бот автоматической модерации правил общения в чате поддержки.\n\n"
        f"📌 *Доступные команды в личных сообщениях:*\n"
        f"• `/mystats` — посмотреть вашу статистику нарушений и дату сброса счётчика.\n"
        f"• `/help` — информация о правилах и поддержке."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help command."""
    text = (
        "ℹ️ *Правила модерации мата в чате поддержки:*\n\n"
        "Для сохранения безопасной и корректной атмосферы в чате действует лестница предупреждений за мат:\n"
        "1️⃣ **1-е нарушение** — Предупреждение в чате с просьбой удалить или заменить слово.\n"
        "2️⃣ **2-е нарушение** — Удаление матерного сообщения ботом.\n"
        "3️⃣ **3-е нарушение** — Временное исключение из группы (кик).\n"
        "4️⃣ **4-е нарушение** — Бан в группе на 30 дней.\n\n"
        "🔄 *Сброс счётчика:* Счётчик нарушений обнуляется автоматической системой, если вы не нарушали правила **30 дней подряд**."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /mystats command.
    Shows user their violation count, last violation timestamp, and days left until reset.
    Works best in PM to avoid cluttering group chat.
    """
    user = update.effective_user
    if not user:
        return

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
        text = "✅ **Ваша статистика чистоты:**\nУ вас **0** нарушений правил общения. Спасибо за соблюдение правил!"
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
                formatted_date = last_violation_str
        else:
            formatted_date = "неизвестно"

        banned_until_str = viol_data.get("banned_until")
        ban_info = ""
        if banned_until_str:
            try:
                ban_dt = datetime.fromisoformat(banned_until_str)
                ban_info = f"\n⛔ **Текущий бан до:** `{ban_dt.strftime('%d.%m.%Y %H:%M UTC')}`"
            except Exception:
                pass

        text = (
            f"📊 **Ваша статистика нарушений:**\n\n"
            f"• Текущее количество нарушений: **{count} / 4**\n"
            f"• Дата последнего нарушения: `{formatted_date}`\n"
            f"• Дней до автосброса счётчика (при вежливом общении): **{days_left} дн.**"
            f"{ban_info}"
        )

    # Deliver response
    target_chat_id = user.id if update.effective_chat.type != "private" else update.effective_chat.id
    try:
        await context.bot.send_message(chat_id=target_chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error sending /mystats: {e}")
        await update.message.reply_text(text, parse_mode="Markdown")
