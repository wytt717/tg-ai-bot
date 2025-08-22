import httpx
from typing import List, Dict, Any, Union
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, AI_TIMEOUT

import logging
logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
}

def _messages(user_text: str) -> List[Dict[str, str]]:
    return [{"role": "user", "content": user_text}]


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    # Универсальный async-метод: принимает либо строку, либо готовый список сообщений
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

        logger.info("== ОТПРАВЛЯЕМ ЗАПРОС В AI ==")
        logger.info("URL: %s", f"{self.base_url}/chat/completions")
        logger.info("HEADERS: %s", HEADERS)
        logger.info("PAYLOAD: %s", payload)

        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=HEADERS, json=payload)

            logger.info("== ОТВЕТ ОТ AI ==")
            logger.info("Status: %s", resp.status_code)
            logger.info("Body: %s", resp.text)

            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    # Для обратной совместимости — твой старый метод
    async def chat_completion_async(self, user_text: str) -> str:
        return await self.chat(OPENAI_MODEL, _messages(user_text))

    def chat_completion_sync(self, user_text: str) -> str:
        payload: Dict[str, Any] = {
            "model": OPENAI_MODEL,
            "messages": _messages(user_text),
            "temperature": 0.7,
            "stream": False,
        }

        logger.info("== ОТПРАВЛЯЕМ ЗАПРОС В AI ==")
        logger.info("URL: %s", f"{self.base_url}/chat/completions")
        logger.info("HEADERS: %s", HEADERS)
        logger.info("PAYLOAD: %s", payload)

        with httpx.Client(timeout=AI_TIMEOUT) as client:
            resp = client.post(f"{self.base_url}/chat/completions", headers=HEADERS, json=payload)

            logger.info("== ОТВЕТ ОТ AI ==")
            logger.info("Status: %s", resp.status_code)
            logger.info("Body: %s", resp.text)

            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        
    # ... весь твой текущий код остаётся без изменений выше ...

# Инициализируем клиент один раз
_client = OpenAICompatibleClient(OPENAI_BASE_URL, OPENAI_API_KEY)

async def ask_ai(user_text: str) -> str:
    """
    Универсальная функция для запроса к AI.
    Совместима с импортом из handlers.py.
    """
    return await _client.chat(OPENAI_MODEL, user_text)

