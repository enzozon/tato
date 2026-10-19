from datetime import date, datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
)
from sqlmodel import Field

from app.models.base import Record, TenantRecord


class User(Record, table=True):
    __tablename__: ClassVar[str] = "users"
    onboarding_completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    deletion_requested_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )


class Account(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        CheckConstraint("currency = 'BRL'", name="currency"),
        CheckConstraint("kind IN ('checking', 'savings', 'credit_card', 'cash')", name="kind"),
    )
    name_ciphertext: bytes
    kind: str = Field(max_length=20)
    currency: str = Field(default="BRL", max_length=3)
    opening_balance_cents: int = Field(default=0, sa_type=BigInteger)
    opening_date: date


class Category(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "name"),
        CheckConstraint("length(trim(name)) > 0", name="name"),
    )
    name: str = Field(min_length=1, max_length=80)


class Transaction(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        ForeignKeyConstraint(["user_id", "document_id"], ["documents.user_id", "documents.id"]),
        Index("ix_transactions_user_document", "user_id", "document_id"),
        ForeignKeyConstraint(["user_id", "account_id"], ["accounts.user_id", "accounts.id"]),
        ForeignKeyConstraint(["user_id", "category_id"], ["categories.user_id", "categories.id"]),
        UniqueConstraint("user_id", "account_id", "dedup_key"),
        CheckConstraint(
            "(kind = 'income' AND amount_cents > 0) OR "
            "(kind = 'expense' AND amount_cents < 0) OR "
            "(kind = 'transfer' AND amount_cents <> 0)",
            name="amount_kind",
        ),
        CheckConstraint("dedup_key ~ '^[0-9a-f]{64}$'", name="dedup_key"),
        Index("ix_transactions_user_date", "user_id", "booked_on", "id"),
        Index("ix_transactions_user_account_date", "user_id", "account_id", "booked_on"),
        Index("ix_transactions_user_category", "user_id", "category_id"),
    )
    account_id: UUID
    document_id: UUID | None = None
    category_id: UUID | None = None
    booked_on: date
    amount_cents: int = Field(sa_type=BigInteger)
    kind: str = Field(max_length=10)
    description_ciphertext: bytes
    dedup_key: str = Field(max_length=64)


class DeletedTransaction(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "deleted_transactions"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "account_id"], ["accounts.user_id", "accounts.id"]),
        UniqueConstraint("user_id", "account_id", "dedup_key"),
        CheckConstraint("dedup_key ~ '^[0-9a-f]{64}$'", name="dedup_key"),
    )
    account_id: UUID
    dedup_key: str = Field(max_length=64)


class Reconciliation(TenantRecord, table=True):
    __tablename__: ClassVar[str] = "reconciliations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "debit_transaction_id"],
            ["transactions.user_id", "transactions.id"],
            name="fk_reconciliations_debit",
        ),
        ForeignKeyConstraint(
            ["user_id", "credit_transaction_id"],
            ["transactions.user_id", "transactions.id"],
            name="fk_reconciliations_credit",
        ),
        UniqueConstraint("user_id", "debit_transaction_id"),
        UniqueConstraint("user_id", "credit_transaction_id"),
        CheckConstraint("debit_transaction_id <> credit_transaction_id", name="distinct_legs"),
        CheckConstraint("kind IN ('transfer', 'card_payment')", name="kind"),
        CheckConstraint("debit_previous_kind IN ('expense', 'transfer')", name="debit_kind"),
        CheckConstraint("credit_previous_kind IN ('income', 'transfer')", name="credit_kind"),
    )
    debit_transaction_id: UUID
    credit_transaction_id: UUID
    kind: str = Field(max_length=16)
    debit_previous_kind: str = Field(max_length=10)
    credit_previous_kind: str = Field(max_length=10)
