import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def identity() -> dict[str, object]:
    path = Path(__file__).resolve().parents[3] / "packages/mascot/identity.json"
    value: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return value


def phrase(key: str) -> str:
    data = identity()
    messages = data["messages"]
    if not isinstance(messages, dict) or not isinstance(messages.get(key), str):
        raise ValueError("Frase do mascote ausente.")
    return str(messages[key]).format(name=data["name"])
