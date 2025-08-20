import os
from dotenv import load_dotenv

load_dotenv()  # загрузит .env из корня репозитория

ALLOWED_USERS = {996208453, 580510842} 

# 996208453 - main
# 580510842 - Ali

def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val

# Обязательные переменные
OPENAI_API_KEY = require_env("OPENAI_API_KEY")

# Можно оставить по умолчанию официальный API, если не используешь локальный/совместимый
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Таймаут в секундах
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "60"))

def env_str(key: str, default: str | None = None, required: bool = False) -> str:
    val = os.getenv(key, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Environment variable {key} is required")
    return val or ""

def env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except ValueError:
        return default

def env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except ValueError:
        return default

TELEGRAM_BOT_TOKEN = env_str("TELEGRAM_BOT_TOKEN", required=True)
API_KEY = env_str("OPENAI_API_KEY", required=True)
BASE_URL = env_str("BASE_URL", "https://api.groq.com/openai/v1")
MODEL = env_str("MODEL", "llama-3.1-70b-versatile")
TEMPERATURE = env_float("TEMPERATURE", 0.7)
MAX_HISTORY_CHARS = env_int("MAX_HISTORY_CHARS", 12000)

TG_MAX_MESSAGE_LEN = 4096
SYSTEM_PROMPT = env_str(
    "SYSTEM_PROMPT",
    "You are a helpful, concise assistant. Answer in the user's language."
)
