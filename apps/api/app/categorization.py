import unicodedata
from uuid import UUID

from sqlmodel import Session, col, select

from app.crypto import decrypt_text
from app.models import Rule


def normalize(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    )


def load_rules(session: Session, owner: UUID, key: bytes) -> list[tuple[str, UUID]]:
    rules = session.exec(
        select(Rule)
        .where(Rule.user_id == owner, col(Rule.enabled).is_(True))
        .order_by(col(Rule.priority), col(Rule.id))
        .limit(1001)
    ).all()  # noqa: E712
    if len(rules) > 1000:
        raise ValueError("Limite de regras excedido.")
    return [
        (normalize(decrypt_text(rule.pattern_ciphertext, key, owner, "rule")), rule.category_id)
        for rule in rules
    ]


def match_category(description: str, rules: list[tuple[str, UUID]]) -> UUID | None:
    description = normalize(description)
    for pattern, category in rules:
        if pattern.strip() and pattern in description:
            return category
    return None
