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


# Состояние ИИ для каждого пользователя
_user_ai_enabled = {}


# ---------- Меню ----------
def _main_menu(ai_on: bool) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton("/start")],
        [KeyboardButton("/help")],
        [KeyboardButton("🛑 Выключить ИИ") if ai_on else KeyboardButton("🤖 Включить ИИ")],
        [KeyboardButton("⚙ Настройки"), KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


def _settings_menu() -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton("🔙 Назад")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


async def _deny_if_not_allowed(update: Update) -> bool:
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return True
    return False


# ---------- Хендлеры ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _deny_if_not_allowed(update):
        return
    _user_ai_enabled[update.effective_user.id] = False
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 👋\nВыбери действие:",
        reply_markup=_main_menu(False)
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _deny_if_not_allowed(update):
        return

    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    ai_on = _user_ai_enabled.get(uid, False)

    if text == "🤖 Включить ИИ":
        _user_ai_enabled[uid] = True
        await update.message.reply_text("ИИ включён ✅. Пиши запросы.", reply_markup=_main_menu(True))
        return

    if text == "🛑 Выключить ИИ":
        _user_ai_enabled[uid] = False
        await update.message.reply_text("ИИ выключен ❌.", reply_markup=_main_menu(False))
        return

    if text == "⚙ Настройки":
        await update.message.reply_text("Раздел настроек:", reply_markup=_settings_menu())
        return

    if text == "❓ Помощь":
        await update.message.reply_text("Нажми «Включить ИИ», чтобы получать ответы.")
        return

    if text == "🔙 Назад":
        await update.message.reply_text("Главное меню:", reply_markup=_main_menu(ai_on))
        return

    if not ai_on:
        await update.message.reply_text("Сначала включи ИИ через меню.")
        return

    # --- Работа с памятью пользователя ---
    context_data = None
    if user_memory:
        try:
            user_memory.add_message(uid, "user", text)
            context_data = user_memory.get_context(uid)
        except Exception:
            pass

    # --- Запрос к ИИ ---
    try:
        answer = await ask_ai(user_text=text)
    except TypeError:
        answer = await ask_ai(text)

    if user_memory and answer:
        try:
            user_memory.add_message(uid, "assistant", answer)
        except Exception:
            pass

    if not answer:
        answer = "Не удалось получить ответ. Попробуй ещё раз позже."

    if split_text:
        for part in split_text(answer):
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(answer)


# ---------- Запуск ----------
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    logger.info("Бот запущен. Ожидаю сообщения...")
    app.run_polling()


if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    main()
