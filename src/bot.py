import logging

from telegram import (
    Update,
)
from telegram.ext import (
    ApplicationBuilder,

)

from src.handlers.commands import register_handlers

from src.config import TELEGRAM_BOT_TOKEN, ALLOWED_USERS


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
