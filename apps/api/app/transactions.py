import hashlib
from datetime import date
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator
from sqlalchemy import Engine, and_, or_
from sqlmodel import col, select

from app.account_routes import EngineDep, IdentityDep
from app.account_service import account_session
from app.agent_routes import handled
from app.crypto import decrypt_text, encrypt_text, load_key
from app.llm_service import require_active
from app.models import Account, Category, DeletedTransaction, Transaction
from app.plans import user_plan
from app.rate_limit import check_rate
from app.reconciliation_links import linked_reconciliations

router = APIRouter(prefix="/transactions", tags=["lançamentos"])
Kind = Literal["income", "expense", "transfer"]


class TransactionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: UUID | None = None
    start: date | None = None
    end: date | None = None
    kind: Kind | None = None
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=47)

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.start and self.end and self.end < self.start:
            raise ValueError("O fim não pode ser anterior ao início.")
        if self.cursor:
            day, identifier = self.cursor.split(":")
            date.fromisoformat(day)
            UUID(identifier)
        return self


class TransactionView(BaseModel):
    id: UUID
    account_id: UUID
    booked_on: date
    amount_cents: str
    kind: Kind
    description: str
    category: str | None
    revision: str
    reconciliation_id: UUID | None = None


class TransactionPage(BaseModel):
    items: list[TransactionView]
    next_cursor: str | None


def revision(record: Transaction) -> str:
    return hashlib.sha256(
        record.model_dump_json(exclude={"description_ciphertext"}).encode()
        + record.description_ciphertext
    ).hexdigest()


def view(record: Transaction, category: str | None, key: bytes, owner: UUID) -> TransactionView:
    return TransactionView(
        id=record.id,
        account_id=record.account_id,
        booked_on=record.booked_on,
        amount_cents=str(record.amount_cents),
        kind=cast(Kind, record.kind),
        description=decrypt_text(record.description_ciphertext, key, owner, "transaction"),
        category=category,
        revision=revision(record),
    )


def list_transactions(engine: Engine, owner: UUID, filters: TransactionFilter) -> TransactionPage:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        if (
            filters.account_id
            and session.exec(
                select(Account.id).where(Account.user_id == owner, Account.id == filters.account_id)
            ).first()
            is None
        ):
            raise HTTPException(404, "Conta não encontrada.")
        statement = (
            select(Transaction, Category.name)
            .join(
                Category,
                and_(
                    col(Transaction.category_id) == Category.id,
                    col(Transaction.user_id) == Category.user_id,
                ),
                isouter=True,
            )
            .where(Transaction.user_id == owner)
        )
        if filters.account_id:
            statement = statement.where(Transaction.account_id == filters.account_id)
        if filters.start:
            statement = statement.where(Transaction.booked_on >= filters.start)
        if filters.end:
            statement = statement.where(Transaction.booked_on <= filters.end)
        if filters.kind:
            statement = statement.where(Transaction.kind == filters.kind)
        if filters.cursor:
            day, identifier = filters.cursor.split(":")
            statement = statement.where(
                or_(
                    col(Transaction.booked_on) < date.fromisoformat(day),
                    and_(
                        col(Transaction.booked_on) == date.fromisoformat(day),
                        col(Transaction.id) < UUID(identifier),
                    ),
                )
            )
        rows = session.exec(
            statement.order_by(col(Transaction.booked_on).desc(), col(Transaction.id).desc()).limit(
                filters.limit + 1
            )
        ).all()
        items = [view(record, category, key, owner) for record, category in rows[: filters.limit]]
        links = {
            identifier: link.id
            for link in linked_reconciliations(session, owner, [item.id for item in items])
            for identifier in [link.debit_transaction_id, link.credit_transaction_id]
        }
        for item in items:
            item.reconciliation_id = links.get(item.id)
        last = items[-1] if items else None
        return TransactionPage(
            items=items,
            next_cursor=(
                f"{last.booked_on}:{last.id}" if last and len(rows) > filters.limit else None
            ),
        )


class TransactionEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str = Field(pattern="^[0-9a-f]{64}$")
    booked_on: date
    amount_cents: str = Field(pattern="^-?[0-9]{1,19}$")
    kind: Kind
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
    ]
    category: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None
    ) = None

    @model_validator(mode="after")
    def valid_amount(self) -> Self:
        amount = int(self.amount_cents)
        if (
            not -(2**63) <= amount < 2**63
            or amount == 0
            or (self.kind == "expense" and amount > 0)
            or (self.kind == "income" and amount < 0)
        ):
            raise ValueError("Confira o sinal e o limite do valor.")
        return self


def edit_transaction(
    engine: Engine, owner: UUID, identifier: UUID, data: TransactionEdit
) -> TransactionView:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        record = session.exec(
            select(Transaction).where(Transaction.user_id == owner, Transaction.id == identifier)
        ).first()
        if record is None:
            raise HTTPException(404, "Lançamento não encontrado.")
        if linked_reconciliations(session, owner, [identifier]):
            raise HTTPException(409, "Desfaça a reconciliação antes de editar.")
        if revision(record) != data.revision:
            raise HTTPException(409, "O lançamento mudou. Recarregue antes de editar.")
        category = None
        if data.category:
            category = session.exec(
                select(Category).where(Category.user_id == owner, Category.name == data.category)
            ).first()
            if category is None:
                if (
                    len(
                        session.exec(
                            select(Category.id).where(Category.user_id == owner).limit(1000)
                        ).all()
                    )
                    >= 1000
                ):
                    raise HTTPException(409, "Limite técnico de 1000 categorias atingido.")
                category = Category(user_id=owner, name=data.category)
                session.add(category)
                session.flush()
        record.booked_on = data.booked_on
        record.amount_cents = int(data.amount_cents)
        record.kind = data.kind
        record.category_id = category.id if category else None
        record.description_ciphertext = encrypt_text(data.description, key, owner, "transaction")
        session.add(record)
        session.flush()
        return view(record, data.category, key, owner)


class TransactionDeletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str = Field(pattern="^[0-9a-f]{64}$")
    confirm: StrictBool


def delete_transaction(
    engine: Engine, owner: UUID, identifier: UUID, data: TransactionDeletion
) -> None:
    if data.confirm is not True:
        raise HTTPException(422, "Confirme explicitamente a exclusão.")
    with account_session(engine, owner) as session:
        require_active(session, owner)
        check_rate(owner, user_plan(session, owner).requests_per_minute)
        record = session.exec(
            select(Transaction).where(Transaction.user_id == owner, Transaction.id == identifier)
        ).first()
        if record is None:
            removed = session.exec(
                select(DeletedTransaction.id).where(
                    DeletedTransaction.user_id == owner, DeletedTransaction.id == identifier
                )
            ).first()
            if removed is not None:
                return
            raise HTTPException(404, "Lançamento não encontrado.")
        if revision(record) != data.revision:
            raise HTTPException(409, "O lançamento mudou. Recarregue antes de excluir.")
        if linked_reconciliations(session, owner, [identifier]):
            raise HTTPException(409, "Desfaça a reconciliação antes de excluir.")
        session.add(
            DeletedTransaction(
                id=record.id,
                user_id=owner,
                account_id=record.account_id,
                dedup_key=record.dedup_key,
            )
        )
        session.delete(record)
        session.flush()


@router.get("", response_model=TransactionPage)
def get_transactions(
    filters: Annotated[TransactionFilter, Query()],
    identity: IdentityDep,
    engine: EngineDep,
    response: Response,
) -> TransactionPage:
    response.headers["Cache-Control"] = "no-store"
    with handled():
        return list_transactions(engine, identity.id, filters)


@router.put("/{identifier}", response_model=TransactionView)
def put_transaction(
    identifier: UUID,
    data: TransactionEdit,
    identity: IdentityDep,
    engine: EngineDep,
    response: Response,
) -> TransactionView:
    response.headers["Cache-Control"] = "no-store"
    with handled():
        return edit_transaction(engine, identity.id, identifier, data)


@router.delete("/{identifier}", status_code=204)
def remove_transaction(
    identifier: UUID, data: TransactionDeletion, identity: IdentityDep, engine: EngineDep
) -> Response:
    with handled():
        delete_transaction(engine, identity.id, identifier, data)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
