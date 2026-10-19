from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import Engine, or_
from sqlmodel import Session, col, select

from app.account_routes import EngineDep, IdentityDep
from app.account_service import account_session
from app.agent_routes import handled, no_store
from app.crypto import load_key
from app.llm_service import require_active
from app.models import Account, Category, Reconciliation, Transaction
from app.plans import user_plan
from app.rate_limit import check_rate
from app.reconciliation_links import linked_reconciliations
from app.reconciliation_rules import PairImpact, pair_impact
from app.transactions import TransactionView, revision, view

router = APIRouter(
    prefix="/reconciliations", tags=["reconciliação"], dependencies=[Depends(no_store)]
)


class Candidate(BaseModel):
    entry: TransactionView
    impact: PairImpact


class Candidates(BaseModel):
    source: TransactionView
    candidates: list[Candidate]
    truncated: bool


class PairView(BaseModel):
    id: UUID
    debit: TransactionView
    credit: TransactionView
    impact: PairImpact


class PairConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    debit_revision: str = Field(pattern="^[0-9a-f]{64}$")
    credit_revision: str = Field(pattern="^[0-9a-f]{64}$")
    confirm: StrictBool


class PairSelection(PairConfirmation):
    debit_id: UUID
    credit_id: UUID


def authorize(session: Session, owner: UUID) -> None:
    require_active(session, owner)
    check_rate(owner, user_plan(session, owner).requests_per_minute)


def entry(session: Session, owner: UUID, identifier: UUID) -> Transaction:
    record = session.exec(
        select(Transaction).where(Transaction.user_id == owner, Transaction.id == identifier)
    ).first()
    if record is None:
        raise HTTPException(404, "Lançamento não encontrado.")
    return record


def impact(session: Session, owner: UUID, debit: Transaction, credit: Transaction) -> PairImpact:
    outgoing = session.exec(
        select(Account).where(Account.user_id == owner, Account.id == debit.account_id)
    ).one()
    incoming = session.exec(
        select(Account).where(Account.user_id == owner, Account.id == credit.account_id)
    ).one()
    try:
        return pair_impact(debit, credit, outgoing, incoming)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


def public_entry(session: Session, owner: UUID, record: Transaction, key: bytes) -> TransactionView:
    category = (
        session.exec(
            select(Category.name).where(
                Category.user_id == owner, Category.id == record.category_id
            )
        ).first()
        if record.category_id
        else None
    )
    return view(record, category, key, owner)


def pair_view(session: Session, owner: UUID, link: Reconciliation, key: bytes) -> PairView:
    debit = entry(session, owner, link.debit_transaction_id)
    credit = entry(session, owner, link.credit_transaction_id)
    # A prévia de desfazer usa as naturezas anteriores sem alterar o estado ORM.
    previous_debit = debit.model_copy(update={"kind": link.debit_previous_kind})
    previous_credit = credit.model_copy(update={"kind": link.credit_previous_kind})
    result = impact(session, owner, previous_debit, previous_credit)
    return PairView(
        id=link.id,
        debit=public_entry(session, owner, debit, key),
        credit=public_entry(session, owner, credit, key),
        impact=result,
    )


def candidates(engine: Engine, owner: UUID, debit_id: UUID) -> Candidates:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        authorize(session, owner)
        debit = entry(session, owner, debit_id)
        outgoing = session.get(Account, debit.account_id)
        if debit.amount_cents >= 0 or outgoing is None or outgoing.kind == "credit_card":
            raise HTTPException(422, "Selecione uma saída de conta ou dinheiro.")
        if linked_reconciliations(session, owner, [debit_id]):
            raise HTTPException(409, "Este lançamento já está vinculado.")
        if debit.amount_cents == -(2**63):
            return Candidates(
                source=public_entry(session, owner, debit, key), candidates=[], truncated=False
            )
        linked = (
            select(Reconciliation.id)
            .where(
                Reconciliation.user_id == owner,
                or_(
                    col(Reconciliation.debit_transaction_id) == Transaction.id,
                    col(Reconciliation.credit_transaction_id) == Transaction.id,
                ),
            )
            .exists()
        )
        low = date.fromordinal(max(date.min.toordinal(), debit.booked_on.toordinal() - 7))
        high = date.fromordinal(min(date.max.toordinal(), debit.booked_on.toordinal() + 7))
        rows = session.exec(
            select(Transaction)
            .where(
                Transaction.user_id == owner,
                Transaction.account_id != debit.account_id,
                Transaction.amount_cents == -debit.amount_cents,
                Transaction.booked_on >= low,
                Transaction.booked_on <= high,
                ~linked,
            )
            .order_by(col(Transaction.booked_on).desc(), col(Transaction.id).desc())
            .limit(21)
        ).all()
        found = [
            Candidate(
                entry=public_entry(session, owner, row, key),
                impact=impact(session, owner, debit, row),
            )
            for row in rows[:20]
        ]
        return Candidates(
            source=public_entry(session, owner, debit, key),
            candidates=found,
            truncated=len(rows) > 20,
        )


def get_pair(engine: Engine, owner: UUID, identifier: UUID) -> PairView:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        authorize(session, owner)
        link = session.exec(
            select(Reconciliation).where(
                Reconciliation.user_id == owner, Reconciliation.id == identifier
            )
        ).first()
        if link is None:
            raise HTTPException(404, "Vínculo não encontrado.")
        return pair_view(session, owner, link, key)


def verify(data: PairConfirmation, debit: Transaction, credit: Transaction) -> None:
    if data.confirm is not True:
        raise HTTPException(422, "Confirme explicitamente a reconciliação.")
    if revision(debit) != data.debit_revision or revision(credit) != data.credit_revision:
        raise HTTPException(409, "Os registros mudaram. Recarregue a prévia.")


def reconcile(engine: Engine, owner: UUID, data: PairSelection) -> PairView:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        authorize(session, owner)
        debit, credit = entry(session, owner, data.debit_id), entry(session, owner, data.credit_id)
        if data.confirm is not True:
            raise HTTPException(422, "Confirme explicitamente a reconciliação.")
        links = linked_reconciliations(session, owner, [debit.id, credit.id])
        if links:
            if (
                len(links) == 1
                and links[0].debit_transaction_id == debit.id
                and links[0].credit_transaction_id == credit.id
            ):
                return pair_view(session, owner, links[0], key)
            raise HTTPException(409, "Uma das pontas já está vinculada.")
        verify(data, debit, credit)
        result = impact(session, owner, debit, credit)
        link = Reconciliation(
            user_id=owner,
            debit_transaction_id=debit.id,
            credit_transaction_id=credit.id,
            kind=result.kind,
            debit_previous_kind=debit.kind,
            credit_previous_kind=credit.kind,
        )
        debit.kind = credit.kind = "transfer"
        session.add_all([debit, credit, link])
        session.flush()
        return pair_view(session, owner, link, key)


def undo(engine: Engine, owner: UUID, identifier: UUID, data: PairConfirmation) -> None:
    if data.confirm is not True:
        raise HTTPException(422, "Confirme explicitamente desfazer.")
    with account_session(engine, owner) as session:
        authorize(session, owner)
        link = session.exec(
            select(Reconciliation).where(
                Reconciliation.user_id == owner, Reconciliation.id == identifier
            )
        ).first()
        if link is None:
            return
        debit, credit = (
            entry(session, owner, link.debit_transaction_id),
            entry(session, owner, link.credit_transaction_id),
        )
        verify(data, debit, credit)
        if debit.kind != "transfer" or credit.kind != "transfer":
            raise HTTPException(409, "Classificação divergente; revise os registros.")
        debit.kind, credit.kind = link.debit_previous_kind, link.credit_previous_kind
        session.add_all([debit, credit])
        session.delete(link)
        session.flush()


@router.get("/candidates", response_model=Candidates)
def get_candidates(debit_id: UUID, identity: IdentityDep, engine: EngineDep) -> Candidates:
    with handled():
        return candidates(engine, identity.id, debit_id)


@router.get("/{identifier}", response_model=PairView)
def get_reconciliation(identifier: UUID, identity: IdentityDep, engine: EngineDep) -> PairView:
    with handled():
        return get_pair(engine, identity.id, identifier)


@router.post("", response_model=PairView)
def post_reconciliation(data: PairSelection, identity: IdentityDep, engine: EngineDep) -> PairView:
    with handled():
        return reconcile(engine, identity.id, data)


@router.delete("/{identifier}", status_code=204)
def delete_reconciliation(
    identifier: UUID, data: PairConfirmation, identity: IdentityDep, engine: EngineDep
) -> Response:
    with handled():
        undo(engine, identity.id, identifier, data)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
