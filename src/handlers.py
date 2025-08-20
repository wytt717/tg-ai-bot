from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes
from config import ALLOWED_USERS  
from  bot import main_menu_markup
import asyncio, httpx
from .bot import send_typing, generate_ai_reply, chunk_text, TG_MAX_MESSAGE_LEN, safe_reply


history = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["💬 Начать диалог", "⚙️ Настройки"],
        ["❓ Помощь"]
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=markup)
    context.user_data["mode"] = "menu"

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Доступ
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return

    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Режимы
    mode = context.user_data.get("mode", "menu")
    enabled = context.user_data.get("enabled", True)

    # Меню выбора: не стартуем диалог сразу
    if mode == "menu":
        if text == "💬 Начать диалог":
            context.user_data["mode"] = "dialog"
            await update.message.reply_text("Диалог запущен. Напиши свой запрос.")
            return
        if text == "⚙️ Настройки":
            await show_settings(update, context)
            return
        if text == "❓ Помощь":
            await update.message.reply_text(
                "Я отвечаю на вопросы с помощью ИИ.\n"
                "• Выбери «Начать диалог», чтобы общаться\n"
                "• Открой «Настройки», чтобы включить/выключить бота или очистить контекст",
                reply_markup=main_menu_markup()
            )
            return
        # Любой другой текст в меню — просим выбрать опцию
        await update.message.reply_text("Выбери действие из меню ниже.", reply_markup=main_menu_markup())
        return

    # Если бот выключен — диалог не ведем
    if not enabled:
        await update.message.reply_text("Бот выключен. Открой «⚙️ Настройки» и включи его.")
        return

    # Режим диалога — здесь оставляем твою текущую логику
    if mode == "dialog":
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


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("🔴 Выключить бота", callback_data="disable_bot")],
        [InlineKeyboardButton("🟢 Включить бота", callback_data="enable_bot")],
        [InlineKeyboardButton("🧹 Очистить историю", callback_data="clear_history")]
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Настройки:", reply_markup=markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    if data == "disable_bot":
        context.user_data["enabled"] = False
        await query.edit_message_text("Бот выключен. Нажми /start для повторного запуска.")
    elif data == "enable_bot":
        context.user_data["enabled"] = True
        await query.edit_message_text("Бот включен.")
    elif data == "clear_history":
        history[user_id] = []
        await query.edit_message_text("История очищена.")
