import logging

from telegram import (
    Update,
)
from telegram.ext import (
    ApplicationBuilder,

)

from src.handlers.commands import register_handlers

from src.config import TELEGRAM_BOT_TOKEN


# Логирование
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
