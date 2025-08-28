from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from src.utils.access import deny_if_not_allowed
from src.ai_providers.openai_compatible import ask_ai
import logging

try:
    from src.utils.memory import user_memory
except ImportError:
    user_memory = None

try:
    from src.utils.chunking import split_text
except ImportError:
    split_text = None

from telegram.constants import ParseMode  # ✅ для HTML форматирования


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import json
# Храним состояние включён/выключен ИИ по пользователю
_user_ai_enabled = {}



import os


from src.ai_providers.openai_compatible import ask_ai

def _inline_main_menu(ai_on: bool) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("🚀 Запустить бота", callback_data="start_bot")],
        [InlineKeyboardButton("🛑 Выключить ИИ" if ai_on else "🤖 Включить ИИ", callback_data="toggle_ai")],
        [
            InlineKeyboardButton("⚙ Настройки", callback_data="settings"),
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(kb)

# обработчик команд (например, /start)
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ai_on = _user_ai_enabled.get(user_id, False)

    await update.message.reply_text(
        "Привет! Вот твоё меню:",
        reply_markup=_inline_main_menu(ai_on)
    )

# обработчик нажатий на кнопки
async def inline_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    ai_on = _user_ai_enabled.get(user_id, False)

    if query.data == "start_bot":
        await query.edit_message_text(
            "Бот запущен ✅",
            reply_markup=_inline_main_menu(ai_on)
        )

    elif query.data == "toggle_ai":
        ai_on = not ai_on
        _user_ai_enabled[user_id] = ai_on
        await query.edit_message_text(
            f"ИИ {'включён ✅' if ai_on else 'выключен ❌'}",
            reply_markup=_inline_main_menu(ai_on)
        )

    elif query.data == "settings":
        await query.edit_message_text(
            "Раздел настроек 🛠",
            reply_markup=_inline_main_menu(ai_on)
        )

    elif query.data == "help":
        await query.edit_message_text(
            "Раздел помощи ℹ️",
            reply_markup=_inline_main_menu(ai_on)
        )

# регистрация хендлеров в основном файле
def register_handlers(app):
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(inline_menu_handler))