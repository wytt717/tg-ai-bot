import logging
import asyncio
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from src.handlers.commands import register_handlers

from src.config import TELEGRAM_BOT_TOKEN, ALLOWED_USERS
from src.ai_providers.openai_compatible import ask_ai

try:
    from src.utils.memory import user_memory
except ImportError:
    user_memory = None

try:
    from src.utils.chunking import split_text
except ImportError:
    split_text = None


# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("tg-ai-bot")





async def _deny_if_not_allowed(update: Update) -> bool:
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return True
    return False



# ---------- Запуск ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("tg-ai-bot")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрируем хендлеры централизованно
    register_handlers(app)

    logger.info("Бот запущен. Ожидаю сообщения...")
    app.run_polling()


if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    main()
