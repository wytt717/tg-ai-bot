from collections import defaultdict, deque

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
