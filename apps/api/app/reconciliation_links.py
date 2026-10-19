from uuid import UUID

from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.models import Reconciliation


def linked_reconciliations(
    session: Session, owner: UUID, identifiers: list[UUID]
) -> list[Reconciliation]:
    if not identifiers:
        return []
    return list(
        session.exec(
            select(Reconciliation).where(
                Reconciliation.user_id == owner,
                or_(
                    col(Reconciliation.debit_transaction_id).in_(identifiers),
                    col(Reconciliation.credit_transaction_id).in_(identifiers),
                ),
            )
        ).all()
    )


def original_kinds(session: Session, owner: UUID, identifiers: list[UUID]) -> dict[UUID, str]:
    return {
        identifier: kind
        for link in linked_reconciliations(session, owner, identifiers)
        for identifier, kind in [
            (link.debit_transaction_id, link.debit_previous_kind),
            (link.credit_transaction_id, link.credit_previous_kind),
        ]
    }
