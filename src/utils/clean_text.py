import re
import unicodedata

_ALLOWED_CLASS = (
    r'[^\u0000-\u007F'   # ASCII (латиница, цифры, базовая пунктуация)
    r'\u0400-\u04FF'     # Кириллица (основной блок)
    r'\u0500-\u052F'     # Кириллица (доп. блок)
    r'\u2DE0-\u2DFF'     # Кириллица Extended-A
    r'\uA640-\uA69F'     # Кириллица Extended-B
    r'\s.,!?;:()'

)

def clean_ai_text(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    return re.sub(_ALLOWED_CLASS, '', text)
