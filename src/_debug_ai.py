import asyncio
from src.ai_providers.openai_compatible import chat_completion_async, chat_completion_sync
from src.config import OPENAI_BASE_URL, OPENAI_MODEL

def run_sync():
    print("BASE_URL:", OPENAI_BASE_URL)
    print("MODEL   :", OPENAI_MODEL)
    print("SYNC TEST…")
    out = chat_completion_sync("Ответь словом: pong")
    print("REPLY:", out)

async def run_async():
    print("BASE_URL:", OPENAI_BASE_URL)
    print("MODEL   :", OPENAI_MODEL)
    print("ASYNC TEST…")
    out = await chat_completion_async("Ответь словом: pong")
    print("REPLY:", out)

if __name__ == "__main__":
    # Выбери один из вариантов:
    # run_sync()
    asyncio.run(run_async())
