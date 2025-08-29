from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from src.ai_providers.openai_compatible import ask_ai, SYSTEM_PROMPT
from src.utils.access import deny_if_not_allowed

import re

try:
    from src.utils.memory import user_memory
except ImportError:
    user_memory = None

from telegram.constants import ParseMode  # ✅ для HTML форматирования


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

# Храним состояние включён/выключен ИИ по пользователю
_user_ai_enabled = {}
_user_settings = {}  # user_id -> {"model": "...", "lang": "...", "spec": "..."}

_last_ai_response = {}  # user_id -> {"text": str, "msg_id": int}

callback_data="menu_open_from_dialog"


def _inline_main_menu(user_id: int) -> InlineKeyboardMarkup:
    ai_on = _user_ai_enabled.get(user_id, False)
    kb = [
        [InlineKeyboardButton("🚀 Запустить бота", callback_data="start_bot")],
        [InlineKeyboardButton("🛑 Выключить ИИ" if ai_on else "🤖 Включить ИИ", callback_data="toggle_ai")],
        [
        InlineKeyboardButton("⚙ Настройки", callback_data="settings"),
        InlineKeyboardButton("❓ Помощь", callback_data="help")
        ],

    ]
    return InlineKeyboardMarkup(kb)

def _inline_settings_menu(user_id: int) -> InlineKeyboardMarkup:
    settings = _user_settings.get(user_id, {"model": "—", "lang": "—", "spec": "—"})
    kb = [
        [InlineKeyboardButton(f"Модель: {settings['model']}", callback_data="settings_model")],
        [InlineKeyboardButton(f"Язык: {settings['lang']}", callback_data="settings_lang")],
        [InlineKeyboardButton(f"Специализация: {settings['spec']}", callback_data="settings_spec")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(kb)

# /start
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny_if_not_allowed(update):
        return  # прерываем выполнение, если нет доступа
    
    user_id = update.effective_user.id
    _user_ai_enabled.setdefault(user_id, False)
    _user_settings.setdefault(user_id, {"model": "—", "lang": "—", "spec": "—"})
    await update.message.reply_text(
        "Привет! Вот твоё меню:",
        reply_markup=_inline_main_menu(user_id)
    )

# компактное меню (при общении)
async def menu_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает краткое меню / статус в процессе общения"""
    user_id = update.effective_user.id
    ai_on = _user_ai_enabled.get(user_id, False)
    settings = _user_settings.get(user_id, {"model": "—", "lang": "—"})
    await update.message.reply_text(
        f"🤖 ИИ: {'Вкл' if ai_on else 'Выкл'} | {settings['model']} | {settings['lang']}\n"
        "Нажми /menu, чтобы открыть полное меню."
    )


def sanitize_text(s: str, lang: str) -> str:
    if lang.lower().startswith("ru"):
        # только кириллица + базовые знаки препинания
        return re.sub(r"[^А-Яа-яЁё0-9\s.,:;!?()\[\]«»\"'—\-…]", "", s)
    elif lang.lower().startswith("en"):
        # только латиница + базовые знаки препинания
        return re.sub(r"[^A-Za-z0-9\s.,:;!?()\[\]\"'—\-…]", "", s)
    else:
        # без фильтра — если язык не поддерживается или многоязычный
        return s

# чат с ИИ
async def ai_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _user_ai_enabled.get(user_id, False):
        return await menu_status_handler(update, context)

    prompt = update.message.text
    settings = _user_settings.get(user_id, {"model": "—", "lang": "—", "spec": "—"})

    # --- Работа с памятью ---
    context_data = None
    if user_memory:
        try:
            # сохраняем текущее сообщение пользователя
            user_memory.add_message(user_id, "user", prompt)
            # достаём историю (например, последние 10 сообщений)
            context_data = user_memory.get_context(user_id)
        except Exception:
            pass

    # системные инструкции из настроек
    system_instructions = []
    if settings["model"] != "—":
        system_instructions.append(f"[Использовать модель: {settings['model']}]")
    if settings["lang"] != "—":
        system_instructions.append(f"[Язык общения: {settings['lang']}]")
    if settings["spec"] != "—":
        system_instructions.append(f"[Специализация: {settings['spec']}]")

    # --- Системный промпт для сохранения контекста ---

    # --- Склеиваем историю в текст ---
    history_text = ""
    if context_data:
        for msg in context_data:
            role = "Пользователь" if msg["role"] == "user" else "ИИ"
            history_text += f"{role}: {msg['content']}\n"

    # --- Итоговый промпт ---
    full_prompt = (
        SYSTEM_PROMPT + "\n" +
        "\n".join(system_instructions) +
        "\n\nИстория диалога:\n" + history_text +
        f"\nПользователь: {prompt}"
    )

    try:
        ai_response = await ask_ai(full_prompt)

        # --- Сохраняем ответ ассистента в память ---
        if user_memory:
            try:
                user_memory.add_message(user_id, "assistant", ai_response)
            except Exception:
                pass

        ai_response = sanitize_text(ai_response, settings["lang"])
        formatted = format_ai_response(ai_response)

        ai_on = _user_ai_enabled.get(user_id, False)
        short_menu = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"🤖 {'Вкл' if ai_on else 'Выкл'} | {settings['model']} | {settings['lang']}",
                callback_data="menu_open"
            )
        ]])

        sent_msg = await update.message.reply_text(
            formatted,
            reply_markup=short_menu,
            parse_mode=ParseMode.HTML
        )

        _last_ai_response[user_id] = {
            "text": ai_response,
            "msg_id": sent_msg.message_id
        }
        context.user_data["from_dialog_session"] = True

    except Exception as e:
        await update.message.reply_text(f"⚠ Ошибка при обращении к ИИ: {e}")


def _inline_main_menu_with_return(user_id: int, from_dialog: bool) -> InlineKeyboardMarkup:
    kb = [list(row) for row in _inline_main_menu(user_id).inline_keyboard]
    if from_dialog and user_id in _last_ai_response:
        kb.append([InlineKeyboardButton("⬅ Вернуться к ответу", callback_data="back_to_answer")])
    return InlineKeyboardMarkup(kb)

# inline меню
async def inline_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await deny_if_not_allowed(update):
        return

    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    from_dialog = context.user_data.get("from_dialog_session", False)

    # Главное меню
    if data == "start_bot":
        await query.edit_message_text("Бот запущен ✅", reply_markup=_inline_main_menu_with_return(user_id, from_dialog))

    elif data == "toggle_ai":
        _user_ai_enabled[user_id] = not _user_ai_enabled.get(user_id, False)
        await query.edit_message_text(
            f"ИИ {'включён ✅' if _user_ai_enabled[user_id] else 'выключен ❌'}",
            reply_markup=_inline_main_menu_with_return(user_id, from_dialog)
        )

    elif data == "settings":
        await query.edit_message_text("Раздел настроек 🛠", reply_markup=_inline_settings_menu(user_id))

    elif data == "help":
        await query.edit_message_text(
            "ℹ Здесь будет текст помощи.\n"
            "Например, как пользоваться ботом.",
            reply_markup=_inline_main_menu_with_return(user_id, from_dialog)
        )

    elif data == "back_main" or data == "menu_open":
        context.user_data["from_dialog_session"] = False
        await query.edit_message_text("Главное меню:", reply_markup=_inline_main_menu_with_return(user_id, False))

    elif data == "back_to_answer":
        last = _last_ai_response.get(user_id)
        if last:
            ai_on = _user_ai_enabled.get(user_id, False)
            settings = _user_settings.get(user_id, {"model": "—", "lang": "—"})
            short_menu = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"{'Вкл' if ai_on else 'Выкл'} | {settings['model']} | {settings['lang']}",
                    callback_data="menu_open"
                )
            ]])
            await query.edit_message_text(last["text"], reply_markup=short_menu)
        context.user_data["from_dialog_session"] = False

    # Настройки: выбор параметров
    elif data == "settings_model":
        await query.edit_message_text(
            "Выберите модель:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("GPT‑4", callback_data="set_model_gpt4")],
                [InlineKeyboardButton("GPT‑3.5", callback_data="set_model_gpt35")],
                [InlineKeyboardButton("⬅ Назад", callback_data="settings")]
            ])
        )

    elif data == "settings_lang":
        await query.edit_message_text(
            "Выберите язык:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Русский", callback_data="set_lang_ru")],
                [InlineKeyboardButton("English", callback_data="set_lang_en")],
                [InlineKeyboardButton("⬅ Назад", callback_data="settings")]
            ])
        )

    elif data == "settings_spec":
        await query.edit_message_text(
            "Выберите специализацию:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Программирование", callback_data="set_spec_code")],
                [InlineKeyboardButton("Маркетинг", callback_data="set_spec_marketing")],
                [InlineKeyboardButton("➕ Добавить свою", callback_data="set_spec_custom")],
                [InlineKeyboardButton("⬅ Назад", callback_data="settings")]
            ])
        )


    # Настройки: сохранение выбора
    elif data == "set_model_gpt4":
        _user_settings[user_id]["model"] = "GPT‑4"
        await query.edit_message_text("✅ Модель установлена: GPT‑4", reply_markup=_inline_settings_menu(user_id))

    elif data == "set_model_gpt35":
        _user_settings[user_id]["model"] = "GPT‑3.5"
        await query.edit_message_text("✅ Модель установлена: GPT‑3.5", reply_markup=_inline_settings_menu(user_id))

    elif data == "set_lang_ru":
        _user_settings[user_id]["lang"] = "Русский"
        await query.edit_message_text("✅ Язык установлен: Русский", reply_markup=_inline_settings_menu(user_id))

    elif data == "set_lang_en":
        _user_settings[user_id]["lang"] = "English"
        await query.edit_message_text("✅ Language set: English", reply_markup=_inline_settings_menu(user_id))

    elif data == "set_spec_code":
        _user_settings[user_id]["spec"] = "Программирование"
        await query.edit_message_text("✅ Специализация: Программирование", reply_markup=_inline_settings_menu(user_id))

    elif data == "set_spec_marketing":
        _user_settings[user_id]["spec"] = "Маркетинг"
        await query.edit_message_text("✅ Специализация: Маркетинг", reply_markup=_inline_settings_menu(user_id))
    
    elif data == "set_spec_custom":
        context.user_data["awaiting_custom_spec"] = True
        await query.edit_message_text(
            "✍️ Введите свою специализацию (например: «Финансовый анализ» или «UX-дизайн»):"
        )  

    else:
        await query.answer("Неизвестная команда кнопки", show_alert=True)

async def custom_spec_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if context.user_data.get("awaiting_custom_spec"):
        custom_spec = update.message.text.strip()
        _user_settings[user_id]["spec"] = custom_spec
        context.user_data["awaiting_custom_spec"] = False

        await update.message.reply_text(
            f"✅ Специализация установлена: <b>{custom_spec}</b>",
            reply_markup=_inline_settings_menu(user_id),
            parse_mode=ParseMode.HTML
        )
        return

    # если не ждём ввод — передаём в чат с ИИ
    await ai_chat_handler(update, context)


def format_ai_response(text: str) -> str:
    # Markdown -> HTML для выделений
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)




    # Списки
    text = re.sub(r"^\s*[\*\-]\s+", r"• ", text, flags=re.MULTILINE)
    text = re.sub(r"^(\d+)\.\s+", r"\1) ", text, flags=re.MULTILINE)

    # Кодовые блоки
    def escape_code_block(match):
        code = match.group(1)
        code = code.replace("<", "&lt;").replace(">", "&gt;")
        code = code.strip("\n")
        code = re.sub(r"\n{3,}", "\n\n", code)
        return f"<pre><code>{code}</code></pre>"

    text = re.sub(r"```(.*?)```", escape_code_block, text, flags=re.DOTALL)

    # Однострочный код
    text = re.sub(
        r"`([^`\n]+)`",
        lambda m: f"<code>{m.group(1).replace('<', '&lt;').replace('>', '&gt;')}</code>",
        text
    )

    # Нормализация пустых строк вне кодовых блоков
    def normalize_text_block(block):
        return re.sub(r"\n{3,}", "\n\n", block)

    parts = re.split(r"(<pre><code>.*?</code></pre>)", text, flags=re.DOTALL)
    for i in range(0, len(parts), 2):
        parts[i] = normalize_text_block(parts[i])
    text = "".join(parts)

    return text

# регистрация
def register_handlers(app):
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("menu", start_handler))  # открыть полное меню
    app.add_handler(CallbackQueryHandler(inline_menu_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_spec_handler))
