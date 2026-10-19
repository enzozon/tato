from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.account_service import account_session
from app.crypto import encrypt_text
from app.models import Account, Reconciliation, Transaction, User
from app.transactions import (
    TransactionDeletion,
    TransactionEdit,
    TransactionFilter,
    delete_transaction,
    edit_transaction,
    list_transactions,
)
from tests.integration.test_agent_config import agent_accounts as agent_accounts

pytestmark = pytest.mark.integration


@pytest.fixture
def reconciliation_rows(runtime_engine, owners, agent_accounts, monkeypatch):
    monkeypatch.setattr("app.transactions.check_rate", lambda *args: None)
    rows = []
    for owner, account in zip(owners, agent_accounts, strict=True):
        with account_session(runtime_engine, owner) as session:
            outgoing = session.get(Account, account)
            outgoing.name_ciphertext = encrypt_text("Conta origem", b"x" * 32, owner, "account")
            incoming = Account(
                user_id=owner,
                kind="savings",
                opening_date=date(2026, 1, 1),
                name_ciphertext=encrypt_text("Conta destino", b"x" * 32, owner, "account"),
            )
            session.add_all([outgoing, incoming])
            session.flush()
            entries = []
            for amount, kind, key in [(-4500, "expense", "a"), (4500, "income", "b")]:
                entry = Transaction(
                    user_id=owner,
                    account_id=account if amount < 0 else incoming.id,
                    booked_on=date(2026, 10, 1),
                    amount_cents=amount,
                    kind=kind,
                    dedup_key=key * 64,
                    description_ciphertext=encrypt_text(
                        "Sintético", b"x" * 32, owner, "transaction"
                    ),
                )
                session.add(entry)
                session.flush()
                entries.append(entry)
            rows.append(entries)
    return rows


def test_link_rls_guards_and_cascade(runtime_engine, admin_engine, owners, reconciliation_rows):
    debit, credit = reconciliation_rows[0]
    with account_session(runtime_engine, owners[0]) as session:
        link = Reconciliation(
            user_id=owners[0],
            debit_transaction_id=debit.id,
            credit_transaction_id=credit.id,
            kind="transfer",
            debit_previous_kind="expense",
            credit_previous_kind="income",
        )
        session.add(link)
        session.flush()
    page = list_transactions(runtime_engine, owners[0], TransactionFilter())
    assert len(page.items) == 2 and all(item.reconciliation_id == link.id for item in page.items)
    item = page.items[0]
    with pytest.raises(HTTPException) as blocked:
        edit_transaction(
            runtime_engine,
            owners[0],
            item.id,
            TransactionEdit(
                revision=item.revision,
                booked_on=item.booked_on,
                amount_cents=item.amount_cents,
                kind=item.kind,
                description=item.description,
            ),
        )
    assert blocked.value.status_code == 409
    with pytest.raises(HTTPException) as blocked:
        delete_transaction(
            runtime_engine,
            owners[0],
            item.id,
            TransactionDeletion(revision=item.revision, confirm=True),
        )
    assert blocked.value.status_code == 409
    with account_session(runtime_engine, owners[1]) as session:
        assert session.get(Reconciliation, link.id) is None
    with pytest.raises(IntegrityError), account_session(runtime_engine, owners[1]) as session:
        session.add(
            Reconciliation(
                user_id=owners[1],
                debit_transaction_id=reconciliation_rows[1][0].id,
                credit_transaction_id=credit.id,
                kind="transfer",
                debit_previous_kind="expense",
                credit_previous_kind="income",
            )
        )
        session.flush()
    with Session(admin_engine) as session, session.begin():
        session.execute(delete(User).where(User.id == owners[0]))
    with Session(admin_engine) as session:
        assert session.get(Reconciliation, link.id) is None
