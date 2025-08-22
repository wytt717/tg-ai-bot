from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
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

# Храним состояние включён/выключен ИИ по пользователю
_user_ai_enabled = {}

async def cmd_start(update, context):
    uid = update.effective_user.id

    if uid not in _user_ai_enabled:
        _user_ai_enabled[uid] = False

    await update.message.reply_text(
        "Привет!",
        reply_markup=_main_menu(_user_ai_enabled[uid])
    )

def _main_menu(ai_on: bool) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton("Запустить бота")],
        # [KeyboardButton("/help")],
        [KeyboardButton("🛑 Выключить ИИ") if ai_on else KeyboardButton("🤖 Включить ИИ")],
        [KeyboardButton("⚙ Настройки"), KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def _settings_menu() -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton("🔙 Назад")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny_if_not_allowed(update):
        return
    _user_ai_enabled[update.effective_user.id] = False
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}! 👋\nВыбери действие:",
        reply_markup=_main_menu(False)
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny_if_not_allowed(update):
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

    # Память диалога (если есть)
    context_data = None
    if user_memory:
        try:
            user_memory.add_message(uid, "user", text)
            context_data = user_memory.get_context(uid)
        except Exception:
            pass

    # Вызов ИИ
    try:
        answer = await ask_ai(user_text=text)
    except TypeError:
        answer = await ask_ai(text)
    except Exception:
        answer = "⚠ Не удалось получить ответ от ИИ. Попробуй позже."

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

def register_handlers(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))
