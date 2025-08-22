from telegram import Update
from src.config import ALLOWED_USERS
import logging

logger = logging.getLogger(__name__)

async def deny_if_not_allowed(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        logger.warning(f"⛔ Доступ запрещён для пользователя: {user_id}")
        await update.message.reply_text(
            f"⛔ Доступ запрещён.\nВаш Telegram ID: `{user_id}`\n"
            "Если вы считаете, что это ошибка — свяжитесь с администратором.",
            parse_mode="Markdown"
        )
        return True
    return False
