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

import json
import os


from src.ai_providers.openai_compatible import ask_ai

async def process_user_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    # Получаем настройки пользователя
    settings = get_user_settings(user_id)

    # Передаём их в ask_ai
    response = await ask_ai(
        user_text=text,
        model=settings["model"],
        temperature=settings["temp"]
    )

    await update.message.reply_text(response)


SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "temp": 0.7,
    "history": True,
    "lang": "RU",
    "theme": "light"
}

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_settings, f, ensure_ascii=False, indent=2)

user_settings = load_settings()

def get_user_settings(user_id):
    if str(user_id) not in user_settings:
        user_settings[str(user_id)] = DEFAULT_SETTINGS.copy()
        save_settings()
    return user_settings[str(user_id)]

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


# ====== МЕНЮ ======

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

# ====== ЛОКАЛИЗАЦИЯ ======
LANG_TEXTS = {
    "RU": {
        "main_menu": [
            ["Запустить бота"],
            ["🤖 Включить ИИ"],
            ["⚙ Настройки", "❓ Помощь"]
        ],
        "settings_title": "⚙ Настройки",
        "help": "Нажми «Включить ИИ», чтобы получать ответы.",
        "back": "⬅ Назад",
        "lang_changed": "✅ Язык изменён на Русский (RU)."
    },
    "EN": {
        "main_menu": [
            ["Start bot"],
            ["🤖 Enable AI"],
            ["⚙ Settings", "❓ Help"]
        ],
        "settings_title": "⚙ Settings",
        "help": "Press 'Enable AI' to start receiving answers.",
        "back": "⬅ Back",
        "lang_changed": "You've selected English (EN) as your preferred language. How can I assist you today?"
    },
    "DE": {
        "main_menu": [
            ["Bot starten"],
            ["🤖 KI aktivieren"],
            ["⚙ Einstellungen", "❓ Hilfe"]
        ],
        "settings_title": "⚙ Einstellungen",
        "help": "Drücke 'KI aktivieren', um Antworten zu erhalten.",
        "back": "⬅ Zurück",
        "lang_changed": "Sie haben Deutsch (DE) als bevorzugte Sprache ausgewählt."
    }
}

# ====== МЕНЮ ======
def _main_menu(ai_on: bool, lang: str) -> ReplyKeyboardMarkup:
    menu = [row[:] for row in LANG_TEXTS[lang]["main_menu"]]
    if ai_on:
        menu[1][0] = "🛑 Выключить ИИ" if lang == "RU" else ("🛑 Disable AI" if lang == "EN" else "🛑 KI deaktivieren")
    return ReplyKeyboardMarkup(menu, resize_keyboard=True)

def _settings_menu(user_id):
    settings = get_user_settings(user_id)
    lang = settings["lang"]
    return {
        "text": (
            f"{LANG_TEXTS[lang]['settings_title']}\n\n"
            f"Модель: {settings['model']}\n"
            f"Температура: {settings['temp']}\n"
            f"История: {'вкл' if settings['history'] else 'выкл'}\n"
            f"Язык: {settings['lang']}\n"
            f"Тема: {settings['theme']}"
        ),
        "keyboard": [
            ["🤖 Модель ИИ", "🎯 Температура"],
            ["📜 История диалога", "🌐 Язык"],
            ["🎨 Тема", "♻ Сброс настроек"],
            [LANG_TEXTS[lang]["back"]]
        ]
    }

# ====== ОБРАБОТЧИК НАСТРОЕК ======
async def handle_settings(update, uid, text):
    settings = get_user_settings(uid)
    lang = settings["lang"]

    # --- Модель ---
    if text == "🤖 Модель ИИ":
        await update.message.reply_text(
            "Выберите модель:" if lang == "RU" else ("Select model:" if lang == "EN" else "Modell auswählen:"),
            reply_markup=ReplyKeyboardMarkup(
                [["llama3-8b-8192", "mixtral-8x7b-32768"], [LANG_TEXTS[lang]["back"]]],
                resize_keyboard=True
            )
        )
        return True

    if text in ["llama3-8b-8192", "mixtral-8x7b-32768"]:
        settings["model"] = text
        save_settings()
        await update.message.reply_text(
            f"✅ Модель изменена на {text}",
            reply_markup=ReplyKeyboardMarkup(_settings_menu(uid)["keyboard"], resize_keyboard=True)
        )
        return True

    # --- Температура ---
    if text == "🎯 Температура":
        await update.message.reply_text(
            "Выберите температуру:" if lang == "RU" else ("Select temperature:" if lang == "EN" else "Temperatur auswählen:"),
            reply_markup=ReplyKeyboardMarkup([["0.0", "0.7", "1.0"], [LANG_TEXTS[lang]["back"]]], resize_keyboard=True)
        )
        return True

    if text in ["0.0", "0.7", "1.0"]:
        settings["temp"] = float(text)
        save_settings()
        await update.message.reply_text(
            f"✅ Температура изменена на {text}",
            reply_markup=ReplyKeyboardMarkup(_settings_menu(uid)["keyboard"], resize_keyboard=True)
        )
        return True

    # --- История ---
    if text == "📜 История диалога":
        settings["history"] = not settings["history"]
        save_settings()
        await update.message.reply_text(
            f"📜 История теперь {'включена' if settings['history'] else 'выключена'}",
            reply_markup=ReplyKeyboardMarkup(_settings_menu(uid)["keyboard"], resize_keyboard=True)
        )
        return True

    # --- Язык ---
    if text == "🌐 Язык":
        await update.message.reply_text(
            "Выберите язык:" if lang == "RU" else ("Select language:" if lang == "EN" else "Sprache auswählen:"),
            reply_markup=ReplyKeyboardMarkup([["RU", "EN", "DE"], [LANG_TEXTS[lang]["back"]]], resize_keyboard=True)
        )
        return True

    if text in ["RU", "EN", "DE"]:
        settings["lang"] = text
        save_settings()
        await update.message.reply_text(
            LANG_TEXTS[text]["lang_changed"],
            reply_markup=_main_menu(_user_ai_enabled.get(uid, False), text)
        )
        return True

    # --- Тема ---
    if text == "🎨 Тема":
        await update.message.reply_text(
            "Выберите тему:" if lang == "RU" else ("Select theme:" if lang == "EN" else "Thema auswählen:"),
            reply_markup=ReplyKeyboardMarkup([["light", "dark"], [LANG_TEXTS[lang]["back"]]], resize_keyboard=True)
        )
        return True

    if text in ["light", "dark"]:
        settings["theme"] = text
        save_settings()
        await update.message.reply_text(
            f"✅ Тема изменена на {text}",
            reply_markup=ReplyKeyboardMarkup(_settings_menu(uid)["keyboard"], resize_keyboard=True)
        )
        return True

    # --- Сброс ---
    if text == "♻ Сброс настроек":
        user_settings[str(uid)] = DEFAULT_SETTINGS.copy()
        save_settings()
        await update.message.reply_text(
            "♻ Настройки сброшены" if lang == "RU" else ("♻ Settings reset" if lang == "EN" else "♻ Einstellungen zurückgesetzt"),
            reply_markup=ReplyKeyboardMarkup(_settings_menu(uid)["keyboard"], resize_keyboard=True)
        )
        return True

    return False


# ====== ОБРАБОТЧИК ЗАПРОСА К ИИ ======

async def handle_ai_request(update, uid, text):
    context_data = None
    if user_memory:
        try:
            user_memory.add_message(uid, "user", text)
            context_data = user_memory.get_context(uid)
        except Exception:
            pass

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

# ====== ОБРАБОТЧИК МЕНЮ ======
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny_if_not_allowed(update):
        return

    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    settings = get_user_settings(uid)
    lang = settings["lang"]
    ai_on = _user_ai_enabled.get(uid, False)

    # ==== НАВИГАЦИЯ ====
    if text in [LANG_TEXTS[lang]["back"], "🔙 Назад"]:
        await update.message.reply_text(
            "Главное меню:" if lang == "RU" else ("Main menu:" if lang == "EN" else "Hauptmenü:"),
            reply_markup=_main_menu(ai_on, lang)
        )
        return

    if text in ["⚙ Настройки", "⚙ Settings", "⚙ Einstellungen"]:
        menu = _settings_menu(uid)
        await update.message.reply_text(
            menu["text"],
            reply_markup=ReplyKeyboardMarkup(menu["keyboard"], resize_keyboard=True)
        )
        return

    if text in ["❓ Помощь", "❓ Help", "❓ Hilfe"]:
        await update.message.reply_text(LANG_TEXTS[lang]["help"])
        return

    # ==== ВКЛ/ВЫКЛ ИИ ====
    if text in ["🤖 Включить ИИ", "🤖 Enable AI", "🤖 KI aktivieren"]:
        _user_ai_enabled[uid] = True
        await update.message.reply_text(
            "ИИ включён ✅" if lang == "RU" else ("AI enabled ✅" if lang == "EN" else "KI aktiviert ✅"),
            reply_markup=_main_menu(True, lang)
        )
        return

    if text in ["🛑 Выключить ИИ", "🛑 Disable AI", "🛑 KI deaktivieren"]:
        _user_ai_enabled[uid] = False
        await update.message.reply_text(
            "ИИ выключен ❌" if lang == "RU" else ("AI disabled ❌" if lang == "EN" else "KI deaktiviert ❌"),
            reply_markup=_main_menu(False, lang)
        )
        return

    # ==== НАСТРОЙКИ ====
    if await handle_settings(update, uid, text):
        return

    # ==== ПРОВЕРКА ИИ ====
    if not ai_on:
        await update.message.reply_text(
            "Сначала включи ИИ через меню." if lang == "RU" else ("Please enable AI first." if lang == "EN" else "Bitte aktivieren Sie zuerst die KI.")
        )
        return

    # ==== ВЫЗОВ ИИ ====
    await handle_ai_request(update, uid, text)

# ====== ОБРАБОТЧИК ЗАПРОСА К ИИ ======
async def handle_ai_request(update, uid, text):
    context_data = None
    if user_memory:
        try:
            user_memory.add_message(uid, "user", text)
            context_data = user_memory.get_context(uid)
        except Exception:
            pass

    try:
        settings = get_user_settings(uid)
        answer = await ask_ai(
            user_text=text,
            model=settings["model"],
            temperature=settings["temp"]
        )
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

# ====== РЕГИСТРАЦИЯ ХЕНДЛЕРОВ ======
def register_handlers(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

