from collections import defaultdict, deque


class SimpleMemory:
    def __init__(self, max_messages=10):
        # user_id -> deque([{"role": "user"/"assistant", "content": str}, ...])
        self.storage = defaultdict(lambda: deque(maxlen=max_messages))

    def add_message(self, user_id: int, role: str, content: str):
        """Добавляет сообщение в историю пользователя"""
        self.storage[user_id].append({"role": role, "content": content})

    def get_context(self, user_id: int):
        """Возвращает список сообщений пользователя (история)"""
        return list(self.storage[user_id])

    def clear(self, user_id: int):
        """Очищает историю пользователя"""
        self.storage[user_id].clear()


# Создаём глобальный объект памяти, который импортируется в commands.py
user_memory = SimpleMemory(max_messages=10)

def make_history_store(maxlen: int = 40):
    # history[user_id] -> deque of {"role": "...", "content": "..."}
    return defaultdict(lambda: deque(maxlen=maxlen))

def approx_len(messages: list[dict]) -> int:
    return sum(len(m["content"]) for m in messages)

def build_context(history, user_id: int, system_prompt: str, max_chars: int):
    msgs = [{"role": "system", "content": system_prompt}]
    msgs.extend(history[user_id])
    while (sum(len(m["content"]) for m in msgs) > max_chars) and len(history[user_id]) > 2:
        history[user_id].popleft()
        msgs = [{"role": "system", "content": system_prompt}, *history[user_id]]
    return msgs
