from datetime import date
from uuid import UUID, uuid5

from sqlmodel import SQLModel

from app.crypto import dedup_key, encrypt_text
from app.models import (
    Account,
    Category,
    Chunk,
    Document,
    Goal,
    Insight,
    Rule,
    Subscription,
    Transaction,
    User,
)


def demo_records(owner: UUID, key: bytes, identity_key: bytes) -> list[SQLModel]:
    """Dados exclusivamente sintéticos, com IDs estáveis e ordem de dependências."""
    account, category, document = (
        uuid5(owner, name) for name in ("account", "category", "document")
    )
    return [
        User(id=owner),
        Account(
            id=account,
            user_id=owner,
            kind="cash",
            opening_date=date(2026, 1, 1),
            name_ciphertext=encrypt_text("Carteira demonstrativa", key, owner, "account"),
        ),
        Category(id=category, user_id=owner, name="Mercado"),
        Transaction(
            id=uuid5(owner, "transaction"),
            user_id=owner,
            account_id=account,
            category_id=category,
            booked_on=date(2026, 9, 1),
            amount_cents=-4200,
            kind="expense",
            description_ciphertext=encrypt_text("Compra sintética", key, owner, "transaction"),
            dedup_key=dedup_key(identity_key, owner, account, "demo:1"),
        ),
        Rule(
            id=uuid5(owner, "rule"),
            user_id=owner,
            category_id=category,
            pattern_ciphertext=encrypt_text("mercado", key, owner, "rule"),
        ),
        Goal(
            id=uuid5(owner, "goal"),
            user_id=owner,
            target_cents=100000,
            description_ciphertext=encrypt_text("Meta demonstrativa", key, owner, "goal"),
        ),
        Document(
            id=document,
            user_id=owner,
            kind="note",
            name_ciphertext=encrypt_text("Nota demonstrativa", key, owner, "document_name"),
            content_ciphertext=encrypt_text("Texto sintético", key, owner, "document"),
            digest=dedup_key(identity_key, owner, document, "demo:document"),
        ),
        Chunk(
            id=uuid5(owner, "chunk"),
            user_id=owner,
            document_id=document,
            position=0,
            content_ciphertext=encrypt_text("Texto sintético", key, owner, "chunk"),
        ),
        Insight(
            id=uuid5(owner, "insight"),
            user_id=owner,
            agent_kind="goal",
            event_key="demo:goal",
            content_ciphertext=encrypt_text("Aviso demonstrativo", key, owner, "insight"),
        ),
        Subscription(id=uuid5(owner, "subscription"), user_id=owner),
    ]
