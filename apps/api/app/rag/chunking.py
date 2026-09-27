import re
from dataclasses import dataclass

from tokenizers import Tokenizer


@dataclass(frozen=True)
class TextChunk:
    section: str
    text: str
    tokens: int


def chunk_markdown(text: str, tokenizer: Tokenizer, target: int = 480) -> list[TextChunk]:
    if tokenizer.truncation is not None or tokenizer.padding is not None:
        raise ValueError("Contagem exige tokenizer sem truncamento nem padding.")
    if not 32 <= target <= 480 or len(text) > 200000 or "\x00" in text:
        raise ValueError("Documento ou tamanho alvo inválido.")

    def count(value: str) -> int:
        return len(tokenizer.encode(value, add_special_tokens=False).ids)

    sections: list[tuple[str, str]] = []
    title = "Documento"
    lines: list[str] = []
    for line in text.splitlines():
        if heading := re.match(r"^#{1,6}\s+(.+?)\s*$", line):
            sections.append((title, "\n".join(lines)))
            title, lines = heading[1], []
            if len(title) > 200:
                raise ValueError("Título de seção maior que 200 caracteres.")
        else:
            lines.append(line)
    sections.append((title, "\n".join(lines)))
    chunks: list[TextChunk] = []
    overlap = int(target * 0.15)
    for title, content in sections:
        buffer = ""
        units = re.split(r"(?<=[.!?])\s+|\n\s*\n", content.strip())
        for unit in units:
            # Frases longas usam fronteiras de palavra; nunca corte por caractere.
            parts = unit.split() if count(unit) > target else [unit.strip()]
            for part in parts:
                if not part:
                    continue
                if count(part) > target:
                    raise ValueError("Palavra excede a janela; revise o documento.")
                candidate = f"{buffer} {part}".strip()
                if count(candidate) <= target:
                    buffer = candidate
                    continue
                chunks.append(TextChunk(title, buffer, count(buffer)))
                words = buffer.split()
                tail: list[str] = []
                for word in reversed(words):
                    if count(" ".join([word, *tail])) > overlap:
                        break
                    tail.insert(0, word)
                while tail and count(" ".join([*tail, part])) > target:
                    tail.pop(0)
                buffer = " ".join([*tail, part])
        if buffer:
            chunks.append(TextChunk(title, buffer, count(buffer)))
    return chunks
