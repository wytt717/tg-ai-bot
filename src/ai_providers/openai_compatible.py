import os
import itertools
import httpx
import re
import base64
from typing import List, Dict, Any, Union
from src.config import OPENAI_BASE_URL, OPENAI_MODEL, AI_TIMEOUT

import logging
logger = logging.getLogger(__name__)

# ====== Ротация ключей (твоя реализация) ======
API_KEYS = os.getenv("OPENAI_API_KEYS", "").split(",")
API_KEYS = [k.strip() for k in API_KEYS if k.strip()]

if not API_KEYS:
    raise ValueError("Не найдены API ключи в переменной OPENAI_API_KEYS")

_key_cycle = itertools.cycle(API_KEYS)
_current_key = next(_key_cycle)

def get_current_key():
    return _current_key

def rotate_key():
    global _current_key
    _current_key = next(_key_cycle)
    logger.warning(f"[API] Переключение на следующий ключ: {_current_key}")

def make_headers():
    return {
        "Authorization": f"Bearer {_current_key}",
        "Content-Type": "application/json",
    }

# ====== Фильтр-файервол ======
BLOCK_PATTERNS = [
    r"(sk-[A-Za-z0-9]{20,})",  # API ключи
    r"(?:\bpassword\b|\btoken\b|\bapi_key\b)",  # чувствительные слова
    r"(system prompt|hidden prompt|internal instruction)",  # попытка вытащить промпт
]

def sanitize_request(user_input: str) -> str:
    """Маскирует опасные данные"""
    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, user_input, re.IGNORECASE):
            logger.warning("Обнаружен запрещённый паттерн в запросе")
            user_input = re.sub(pattern, "[REDACTED]", user_input, flags=re.IGNORECASE)
    return user_input

def is_request_safe(user_input: str) -> bool:
    """Проверяет, можно ли отправлять запрос"""
    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, user_input, re.IGNORECASE):
            return False
    return True

# ====== Загрузка скрытого системного промпта из .env ======
def load_system_prompt() -> str:
    enc_prompt = os.getenv("SYSTEM_PROMPT_ENC", "")
    if not enc_prompt:
        raise ValueError("Не найден зашифрованный системный промпт в переменной SYSTEM_PROMPT_ENC")
    try:
        decoded_bytes = base64.b64decode(enc_prompt)
        return decoded_bytes.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Ошибка расшифровки системного промпта: {e}")

SYSTEM_PROMPT = load_system_prompt()

def _messages(user_text: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text}
    ]

# ====== Клиент ======
class OpenAICompatibleClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def chat(
        self,
        model: str,
        messages: Union[str, List[Dict[str, str]]],
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        if isinstance(messages, str):
            messages = _messages(messages)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
            "max_tokens": max_tokens,
        }

        # Пробуем столько раз, сколько у нас ключей
        for attempt in range(len(API_KEYS)):
            try:
                async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=make_headers(),
                        json=payload
                    )

                if resp.status_code == 429:  # лимит
                    logger.warning(f"[API] Лимит на ключе {_current_key}, переключаем...")
                    rotate_key()
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning(f"[API] Лимит на ключе {_current_key}, переключаем...")
                    rotate_key()
                    continue
                raise e

        raise RuntimeError("Все API ключи исчерпали лимит")

# ====== Публичная функция ======
_client = OpenAICompatibleClient(OPENAI_BASE_URL)

async def ask_ai(user_text: str, model: str = OPENAI_MODEL, temperature: float = 0.7) -> str:
    clean_text = sanitize_request(user_text)
    if not is_request_safe(clean_text):
        return "Запрос отклонён политикой безопасности."
    return await _client.chat(model, _messages(clean_text), temperature=temperature)
