from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.account_service import account_session
from app.crypto import encrypt_text
from app.models import DeletedTransaction, Transaction, User
from app.repositories import TransactionInput, add_transaction
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


def test_listing_editing_isolation_and_stale_revision(
    runtime_engine, owners, agent_accounts, monkeypatch
):
    monkeypatch.setattr("app.transactions.check_rate", lambda *args: None)
    identifiers = []
    for owner, account in zip(owners, agent_accounts, strict=True):
        with account_session(runtime_engine, owner) as session:
            for day in [1, 2, 3]:
                record = Transaction(
                    user_id=owner,
                    account_id=account,
                    booked_on=date(2026, 10, day),
                    amount_cents=-(2**60),
                    kind="expense",
                    dedup_key=str(day) * 64,
                    description_ciphertext=encrypt_text(
                        "Sintético", b"x" * 32, owner, "transaction"
                    ),
                )
                session.add(record)
                session.flush()
                identifiers.append(record.id)
    first = list_transactions(runtime_engine, owners[0], TransactionFilter(limit=2))
    assert [item.booked_on.day for item in first.items] == [3, 2] and first.next_cursor
    second = list_transactions(
        runtime_engine, owners[0], TransactionFilter(cursor=first.next_cursor)
    )
    assert len(second.items) == 1 and second.items[0].booked_on.day == 1
    assert {item.id for item in first.items}.isdisjoint(item.id for item in second.items)
    assert first.items[0].amount_cents == str(-(2**60))
    with pytest.raises(HTTPException) as missing:
        list_transactions(
            runtime_engine, owners[0], TransactionFilter(account_id=agent_accounts[1])
        )
    assert missing.value.status_code == 404
    item = first.items[0]
    edit = TransactionEdit(
        revision=item.revision,
        booked_on=item.booked_on,
        amount_cents="-4500",
        kind="transfer",
        description="Correção sintética",
        category="Transferências",
    )
    with pytest.raises(HTTPException) as foreign:
        edit_transaction(runtime_engine, owners[1], item.id, edit)
    assert foreign.value.status_code == 404
    result = edit_transaction(runtime_engine, owners[0], item.id, edit)
    assert result.kind == "transfer" and result.amount_cents == "-4500"
    assert result.description == "Correção sintética" and result.category == "Transferências"
    with pytest.raises(HTTPException) as stale:
        edit_transaction(runtime_engine, owners[0], item.id, edit)
    assert stale.value.status_code == 409
    with account_session(runtime_engine, owners[0]) as session:
        record = session.exec(select(Transaction).where(Transaction.id == item.id)).one()
        assert record.dedup_key == "3" * 64
        assert b"Corre" not in record.description_ciphertext
    page = list_transactions(
        runtime_engine,
        owners[0],
        TransactionFilter(
            account_id=agent_accounts[0],
            kind="expense",
            start=date(2026, 10, 2),
            end=date(2026, 10, 2),
        ),
    )
    assert len(page.items) == 1 and page.items[0].booked_on.day == 2


def test_deletion_cannot_reappear_and_preserves_rls(
    runtime_engine, admin_engine, owners, agent_accounts, monkeypatch
):

    monkeypatch.setattr("app.transactions.check_rate", lambda *args: None)
    owner, account = owners[0], agent_accounts[0]
    original = TransactionInput(
        account_id=account,
        booked_on=date(2026, 10, 1),
        kind="expense",
        amount_cents=-5000,
        description="Sintético",
        source_identity="bank:1",
    )
    with account_session(runtime_engine, owner) as session:
        identifier = add_transaction(session, owner, original, b"x" * 32, b"s" * 32)
    item = list_transactions(runtime_engine, owner, TransactionFilter()).items[0]
    data = TransactionDeletion(revision=item.revision, confirm=True)
    with pytest.raises(HTTPException) as foreign:
        delete_transaction(runtime_engine, owners[1], identifier, data)
    assert foreign.value.status_code == 404
    with pytest.raises(HTTPException) as stale:
        delete_transaction(
            runtime_engine, owner, identifier, TransactionDeletion(revision="0" * 64, confirm=True)
        )
    assert stale.value.status_code == 409
    delete_transaction(runtime_engine, owner, identifier, data)
    delete_transaction(runtime_engine, owner, identifier, data)
    with account_session(runtime_engine, owner) as session:
        assert session.get(Transaction, identifier) is None
        removed = session.get(DeletedTransaction, identifier)
        assert removed is not None and removed.account_id == account
        assert add_transaction(session, owner, original, b"x" * 32, b"s" * 32) is None
    with account_session(runtime_engine, owners[1]) as session:
        assert session.get(DeletedTransaction, identifier) is None
    with pytest.raises(IntegrityError), account_session(runtime_engine, owners[1]) as session:
        session.add(DeletedTransaction(user_id=owners[1], account_id=account, dedup_key="1" * 64))
        session.flush()
    with Session(admin_engine) as session, session.begin():
        session.execute(delete(User).where(User.id == owner))
    with Session(admin_engine) as session:
        assert session.get(DeletedTransaction, identifier) is None


def test_deleted_import_stays_removed_in_overlapping_file(
    runtime_engine, owners, agent_accounts, monkeypatch
):
    import base64

    from app.import_parsers import CsvMapping
    from app.import_service import store_import

    monkeypatch.setenv("DEDUP_HMAC_KEY", base64.b64encode(b"s" * 32).decode())
    monkeypatch.setenv("TATO_ENV", "development")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    monkeypatch.setattr("app.transactions.check_rate", lambda *args: None)
    owner, account = owners[0], agent_accounts[0]
    mapping = CsvMapping(
        date_column="date",
        description_column="title",
        amount_column="amount",
        id_column="id",
        decimal_separator=".",
    )
    original = b"date,title,amount,id\n2026-10-01,Mercado sintetico,-45.00,bank-1\n"
    assert (
        store_import(
            runtime_engine, owner, account, original, "original.csv", "csv", mapping
        ).inserted
        == 1
    )
    item = list_transactions(runtime_engine, owner, TransactionFilter()).items[0]
    delete_transaction(
        runtime_engine, owner, item.id, TransactionDeletion(revision=item.revision, confirm=True)
    )
    overlap = original + b"2026-10-02,Compra sintetica,-10.00,bank-2\n"
    result = store_import(runtime_engine, owner, account, overlap, "sobreposto.csv", "csv", mapping)
    assert result.inserted == 1 and result.duplicates == 1
    page = list_transactions(runtime_engine, owner, TransactionFilter())
    assert len(page.items) == 1 and page.items[0].amount_cents == "-1000"
