import asyncio
import re
import html
from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest, TelegramError

import httpx

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters


from .config import (
    TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, OPENAI_BASE_URL,
    OPENAI_MODEL, TEMPERATURE, MAX_HISTORY_CHARS,
    SYSTEM_PROMPT, TG_MAX_MESSAGE_LEN, ALLOWED_USERS
)

from src.utils.chunking import chunk_text
from src.utils.memory import make_history_store, build_context
from src.ai_providers.openai_compatible import OpenAICompatibleClient

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("tg-ai-bot")


# История диалогов
history = make_history_store(maxlen=40)

# Инициализируем клиента
ai = OpenAICompatibleClient(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)


# ----- Меню и настройки -----
# Хелперы для меню и настроек

def main_menu_markup() -> ReplyKeyboardMarkup:
    keyboard = [
        ["💬 Начать диалог", "⚙️ Настройки"],
        ["❓ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def settings_markup() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🔴 Выключить бота", callback_data="disable_bot")],
        [InlineKeyboardButton("🟢 Включить бота", callback_data="enable_bot")],
        [InlineKeyboardButton("🧹 Очистить историю", callback_data="clear_history")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(buttons)


# ---------- Безопасная отправка текста ----------
def _looks_like_code(text: str) -> bool:
    return "```" in text or "`" in text or "<" in text or "&" in text

async def safe_reply(update: Update, text: str):
    try:
        if _looks_like_code(text):
            await update.message.reply_text(text)  # без parse_mode
            return
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except BadRequest:
        try:
            escaped = html.escape(text)
            await update.message.reply_text(escaped, parse_mode=ParseMode.HTML)
        except BadRequest:
            await update.message.reply_text(text)


# ---------- Отправка "печатает..." ----------
async def send_typing(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)


# ---------- Генерация ответа от ИИ ----------
async def generate_ai_reply(user_id: int) -> str:
    msgs = build_context(history, user_id, SYSTEM_PROMPT, MAX_HISTORY_CHARS)

    delay = 1.0
    for attempt in range(3):
        try:
            if hasattr(ai, "chat"):
                logger.info("[AI] call via ai.chat | model=%s | temp=%.2f | msgs=%d",
                            OPENAI_MODEL, TEMPERATURE, len(msgs))
                return await ai.chat(OPENAI_MODEL, msgs, temperature=TEMPERATURE, max_tokens=2048)

            payload = {
                "model": OPENAI_MODEL,
                "messages": msgs,
                "temperature": TEMPERATURE,
                "stream": False,
                "max_tokens": 2048,
            }
            # маскируем ключ
            masked_headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY[:6]}***",
                "Content-Type": "application/json",
            }
            logger.info("[AI] direct httpx call | model=%s | temp=%.2f | msgs=%d | headers=%s",
                        OPENAI_MODEL, TEMPERATURE, len(msgs), masked_headers)

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{OPENAI_BASE_URL}/chat/completions",
                                         headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                                                  "Content-Type": "application/json"},
                                         json=payload)
                logger.info("[AI] status=%s | body_len=%d", resp.status_code, len(resp.text))
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = e.response.text
            logger.warning("[AI] HTTP error on attempt %d: %s | body: %.500s", attempt + 1, status, body)
            if attempt == 2:
                raise
        except Exception as e:
            logger.exception("[AI] call failed on attempt %d: %s", attempt + 1, e)
            if attempt == 2:
                raise

        await asyncio.sleep(delay)
        delay *= 2


# ---------- Команды ----------
# Команда /start: показываем меню и не стартуем диалог

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сбрасываем историю как и раньше
    history[update.effective_user.id].clear()
    # Значения по умолчанию для текущего пользователя
    context.user_data.setdefault("mode", "menu")
    context.user_data.setdefault("enabled", True)

    await update.message.reply_text(
        "Привет! Выбери действие:",
        reply_markup=main_menu_markup()
    )
    context.user_data["mode"] = "menu"


async def show_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Модель: {OPENAI_MODEL}\nТемпература: {TEMPERATURE}")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history[update.effective_user.id].clear()
    await update.message.reply_text("Контекст очищен.")


# ---------- Основной обработчик текста ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return
    
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()
    history[user_id].append({"role": "user", "content": text})

    typing_task = asyncio.create_task(send_typing(update.effective_chat.id, context))
    try:
        ai_answer = await generate_ai_reply(user_id)
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 401:
            msg = "Ошибка авторизации ИИ (проверь ключ API)."
        elif status == 429:
            msg = "Слишком много запросов к ИИ. Подожди немного."
        elif 500 <= status < 600:
            msg = "Сервис ИИ временно недоступен. Попробуй позже."
        else:
            msg = f"Ошибка ИИ ({status})."
        await update.message.reply_text(msg)
        return
    except Exception:
        await update.message.reply_text("Не удалось получить ответ от ИИ. Попробуй через минуту.")
        return
    finally:
        typing_task.cancel()

    history[user_id].append({"role": "assistant", "content": ai_answer})

    for chunk in chunk_text(ai_answer, TG_MAX_MESSAGE_LEN):
        await safe_reply(update, chunk)


# Экран настроек и обработчик inline‑кнопок
async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Настройки:", reply_markup=settings_markup())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        # Вежливое уведомление
        await query.answer("⛔ Нет доступа", show_alert=True)
        return

    data = query.data

    if data == "disable_bot":
        context.user_data["enabled"] = False
        await query.edit_message_text("Бот выключен. Чтобы включить, вернись в настройки.")
        return

    if data == "enable_bot":
        context.user_data["enabled"] = True
        await query.edit_message_text("Бот включен. Можно продолжать диалог.")
        return

    if data == "clear_history":
        history[user_id].clear()
        await query.edit_message_text("История очищена.")
        return

    if data == "back_to_menu":
        context.user_data["mode"] = "menu"
        # Уберём inline‑кнопки и вернемся в меню
        try:
            await query.edit_message_text("Возврат в меню.")
        except Exception:
            pass
        await query.message.reply_text("Выбери действие:", reply_markup=main_menu_markup())
        return
    
# БЫСТРЫЙ ВОЗВРАТ В МЕНЮ
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "menu"
    await update.message.reply_text("Выбери действие:", reply_markup=main_menu_markup())



# ---------- Глобальный обработчик ошибок ----------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Telegram error: %s", context.error)


# ---------- Запуск ----------
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("model", show_model))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
    except Exception:
        pass
    main()
