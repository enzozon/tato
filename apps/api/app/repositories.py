from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.crypto import dedup_key, encrypt_text
from app.models import Chunk, Transaction


class TransactionInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    account_id: UUID
    category_id: UUID | None = None
    booked_on: date
    amount_cents: int = Field(ge=-(2**63), le=2**63 - 1)
    kind: Literal["income", "expense", "transfer"]
    description: str = Field(min_length=1, max_length=5000)
    source_identity: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_amount(self) -> Self:
        if (
            self.amount_cents == 0
            or (self.kind == "income" and self.amount_cents < 0)
            or (self.kind == "expense" and self.amount_cents > 0)
            or not self.description.strip()
            or not self.source_identity.strip()
        ):
            raise ValueError("Confira sinal, descrição e identidade de origem do lançamento.")
        return self


def add_transaction(
    session: Session, owner: UUID, data: TransactionInput, cipher_key: bytes, identity_key: bytes
) -> UUID | None:
    record = Transaction(
        **data.model_dump(exclude={"description", "source_identity"}),
        user_id=owner,
        description_ciphertext=encrypt_text(data.description, cipher_key, owner, "transaction"),
        dedup_key=dedup_key(identity_key, owner, data.account_id, data.source_identity),
    )
    statement = (
        insert(Transaction)
        .values(**record.model_dump())
        .on_conflict_do_nothing(index_elements=["user_id", "account_id", "dedup_key"])
        .returning(col(Transaction.id))
    )
    return session.scalar(statement)


def expense_total(session: Session, owner: UUID, start: date, end: date) -> int:
    """Centavos positivos de despesas no intervalo [start, end)."""
    if end <= start:
        raise ValueError("O fim deve ser posterior ao início.")
    statement = select(func.coalesce(-func.sum(col(Transaction.amount_cents)), 0)).where(
        Transaction.user_id == owner,
        Transaction.kind == "expense",
        Transaction.booked_on >= start,
        Transaction.booked_on < end,
    )
    return int(session.exec(statement).one())


def document_chunks(session: Session, owner: UUID, document_id: UUID) -> list[Chunk]:
    return list(
        session.exec(
            select(Chunk)
            .where(Chunk.user_id == owner, Chunk.document_id == document_id)
            .order_by(col(Chunk.position))
        )
    )
