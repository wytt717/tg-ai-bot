import textwrap

TG_MAX_MESSAGE_LEN = 4096

def chunk_text(text: str, chunk_size: int = TG_MAX_MESSAGE_LEN) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks, buf = [], ""
    for p in paragraphs:
        candidate = (buf + ("\n\n" if buf else "") + p)
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            if buf:
                chunks.append(buf)
                buf = ""
            if len(p) <= chunk_size:
                chunks.append(p)
            else:
                for line in textwrap.wrap(p, width=chunk_size, replace_whitespace=False):
                    chunks.append(line)
    if buf:
        chunks.append(buf)
    return chunks
