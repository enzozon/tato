from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import Engine
from sqlmodel import select

from app.crypto import decrypt_text
from app.database import tenant_session
from app.models import Account, Transaction
from app.repositories import TransactionInput, add_transaction, expense_total

pytestmark = pytest.mark.integration


def test_import_is_idempotent_without_collapsing_equal_purchases(
    runtime_engine: Engine, owners: tuple[UUID, UUID]
) -> None:
    owner, other = owners
    key = b"x" * 32
    with tenant_session(runtime_engine, owner) as session:
        account = Account(
            user_id=owner,
            kind="cash",
            name_ciphertext=b"sintetico",
            opening_date=date(2026, 1, 1),
        )
        session.add(account)
        session.flush()
        data = TransactionInput(
            account_id=account.id,
            booked_on=date(2026, 9, 1),
            amount_cents=-4200,
            kind="expense",
            description="Mercado sintético",
            source_identity="ofx:123",
        )
        assert add_transaction(session, owner, data, key, key) is not None
        assert add_transaction(session, owner, data, key, key) is None
        assert (
            add_transaction(
                session, owner, data.model_copy(update={"source_identity": "ofx:124"}), key, key
            )
            is not None
        )
        transfer = data.model_copy(update={"kind": "transfer", "source_identity": "ofx:125"})
        add_transaction(session, owner, transfer, key, key)
        assert expense_total(session, owner, date(2026, 9, 1), date(2026, 10, 1)) == 8400
        assert expense_total(session, owner, date(2026, 9, 2), date(2026, 10, 1)) == 0
        assert expense_total(session, other, date(2026, 9, 1), date(2026, 10, 1)) == 0
        with pytest.raises(ValueError):
            expense_total(session, owner, date(2026, 9, 1), date(2026, 9, 1))
        for row in session.exec(select(Transaction)):
            assert (
                decrypt_text(row.description_ciphertext, key, owner, "transaction")
                == data.description
            )
