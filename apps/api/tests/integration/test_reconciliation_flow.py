from datetime import date

import pytest
from fastapi import HTTPException

from app.account_service import account_session
from app.dashboard import summary
from app.models import Account, Transaction
from app.reconciliation import (
    PairConfirmation,
    PairSelection,
    candidates,
    get_pair,
    reconcile,
    undo,
)
from tests.integration.test_agent_config import agent_accounts as agent_accounts
from tests.integration.test_reconciliation_schema import reconciliation_rows as reconciliation_rows

pytestmark = pytest.mark.integration


@pytest.fixture
def ready_pairs(reconciliation_rows, monkeypatch):
    monkeypatch.setattr("app.reconciliation.check_rate", lambda *args: None)
    monkeypatch.setattr("app.dashboard.check_rate", lambda *args: None)
    monkeypatch.setenv("TATO_ENV", "development")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    return reconciliation_rows


@pytest.mark.parametrize("card", [False, True])
def test_confirm_and_undo_preserve_balances_and_purchases(
    runtime_engine, owners, ready_pairs, card
):
    debit, credit = ready_pairs[0]
    if card:
        with account_session(runtime_engine, owners[0]) as session:
            account = session.get(Account, credit.account_id)
            account.kind = "credit_card"
            account.opening_balance_cents = -3300
            session.add(account)
            session.add(
                Transaction(
                    user_id=owners[0],
                    account_id=account.id,
                    booked_on=date(2026, 10, 1),
                    amount_cents=-1200,
                    kind="expense",
                    description_ciphertext=debit.description_ciphertext,
                    dedup_key="c" * 64,
                )
            )
    before = summary(runtime_engine, owners[0], date(2026, 10, 10))
    found = candidates(runtime_engine, owners[0], debit.id)
    assert [item.entry.id for item in found.candidates] == [credit.id]
    assert found.candidates[0].impact.kind == ("card_payment" if card else "transfer")
    request = PairSelection(
        debit_id=debit.id,
        credit_id=credit.id,
        debit_revision=found.source.revision,
        credit_revision=found.candidates[0].entry.revision,
        confirm=True,
    )
    with pytest.raises(HTTPException) as stale:
        reconcile(
            runtime_engine, owners[0], request.model_copy(update={"credit_revision": "0" * 64})
        )
    assert stale.value.status_code == 409
    with pytest.raises(HTTPException) as foreign:
        reconcile(runtime_engine, owners[1], request)
    assert foreign.value.status_code == 404
    paired = reconcile(runtime_engine, owners[0], request)
    assert reconcile(runtime_engine, owners[0], request).id == paired.id
    assert paired.debit.kind == paired.credit.kind == "transfer"
    assert paired.impact.expense_reduction_cents == paired.impact.income_reduction_cents == "4500"
    after = summary(runtime_engine, owners[0], date(2026, 10, 10))
    assert after.balance_cents == before.balance_cents
    assert {a.id: a.balance_cents for a in after.accounts} == {
        a.id: a.balance_cents for a in before.accounts
    }
    assert int(before.expense_cents) - int(after.expense_cents) == 4500
    assert after.expense_cents == ("1200" if card else "0")
    with pytest.raises(HTTPException) as linked:
        candidates(runtime_engine, owners[0], debit.id)
    assert linked.value.status_code == 409
    with pytest.raises(HTTPException) as forbidden:
        get_pair(runtime_engine, owners[1], paired.id)
    assert forbidden.value.status_code == 404
    with pytest.raises(HTTPException) as forbidden:
        candidates(runtime_engine, owners[1], debit.id)
    assert forbidden.value.status_code == 404
    current = get_pair(runtime_engine, owners[0], paired.id)
    confirmation = PairConfirmation(
        debit_revision=current.debit.revision, credit_revision=current.credit.revision, confirm=True
    )
    undo(runtime_engine, owners[1], paired.id, confirmation)
    assert get_pair(runtime_engine, owners[0], paired.id).id == paired.id
    with pytest.raises(HTTPException) as stale:
        undo(
            runtime_engine,
            owners[0],
            paired.id,
            confirmation.model_copy(update={"debit_revision": "0" * 64}),
        )
    assert stale.value.status_code == 409
    undo(runtime_engine, owners[0], paired.id, confirmation)
    undo(runtime_engine, owners[0], paired.id, confirmation)
    restored = summary(runtime_engine, owners[0], date(2026, 10, 10))
    assert (
        restored.balance_cents == before.balance_cents
        and restored.expense_cents == before.expense_cents
    )
    assert candidates(runtime_engine, owners[0], debit.id).candidates[0].entry.id == credit.id


def test_overlap_keeps_reconciliation_and_rejects_changed_value(
    runtime_engine, owners, ready_pairs, monkeypatch
):
    import base64

    from app.import_parsers import CsvMapping
    from app.import_service import store_import
    from app.transactions import TransactionFilter, list_transactions

    monkeypatch.setenv("DEDUP_HMAC_KEY", base64.b64encode(b"s" * 32).decode())
    debit, credit = ready_pairs[0]
    mapping = CsvMapping(
        date_column="date",
        description_column="title",
        amount_column="amount",
        id_column="id",
        decimal_separator=".",
    )
    original = b"date,title,amount,id\n2026-10-01,Transferencia sintetica,-45.00,bank-1\n"
    store_import(
        runtime_engine, owners[0], debit.account_id, original, "original.csv", "csv", mapping
    )
    imported = next(
        item
        for item in list_transactions(runtime_engine, owners[0], TransactionFilter()).items
        if item.description == "Transferencia sintetica"
    )
    candidate = candidates(runtime_engine, owners[0], imported.id).candidates[0]
    paired = reconcile(
        runtime_engine,
        owners[0],
        PairSelection(
            debit_id=imported.id,
            credit_id=candidate.entry.id,
            debit_revision=imported.revision,
            credit_revision=candidate.entry.revision,
            confirm=True,
        ),
    )
    overlap = original + b"2026-10-02,Compra sintetica,-10.00,bank-2\n"
    result = store_import(
        runtime_engine, owners[0], debit.account_id, overlap, "sobreposto.csv", "csv", mapping
    )
    assert result.inserted == 1 and result.duplicates == 1
    assert get_pair(runtime_engine, owners[0], paired.id).debit.kind == "transfer"
    with pytest.raises(HTTPException) as conflict:
        store_import(
            runtime_engine,
            owners[0],
            debit.account_id,
            overlap.replace(b"-45.00", b"-46.00"),
            "divergente.csv",
            "csv",
            mapping,
        )
    assert conflict.value.status_code == 409


def test_candidates_limit_and_integer_bound(runtime_engine, owners, ready_pairs):
    debit, credit = ready_pairs[0]
    with account_session(runtime_engine, owners[0]) as session:
        for index in range(22):
            session.add(
                Transaction(
                    user_id=owners[0],
                    account_id=credit.account_id,
                    booked_on=credit.booked_on,
                    amount_cents=4500,
                    kind="income",
                    description_ciphertext=credit.description_ciphertext,
                    dedup_key=f"{index:064x}",
                )
            )
    result = candidates(runtime_engine, owners[0], debit.id)
    assert len(result.candidates) == 20 and result.truncated
    with account_session(runtime_engine, owners[0]) as session:
        record = session.get(Transaction, debit.id)
        record.amount_cents = -(2**63)
        session.add(record)
    assert not candidates(runtime_engine, owners[0], debit.id).candidates


@pytest.mark.parametrize("day", [date.min, date.max])
def test_candidate_dates_are_bounded(runtime_engine, owners, ready_pairs, day):
    debit, credit = ready_pairs[0]
    with account_session(runtime_engine, owners[0]) as session:
        for identifier in [debit.id, credit.id]:
            record = session.get(Transaction, identifier)
            record.booked_on = day
            session.add(record)
    assert candidates(runtime_engine, owners[0], debit.id).candidates[0].entry.id == credit.id


def test_competing_pairs_cannot_reuse_one_leg(runtime_engine, owners, ready_pairs):
    from concurrent.futures import ThreadPoolExecutor

    debit, credit = ready_pairs[0]
    with account_session(runtime_engine, owners[0]) as session:
        extra = Transaction(
            user_id=owners[0],
            account_id=credit.account_id,
            booked_on=credit.booked_on,
            amount_cents=credit.amount_cents,
            kind="income",
            dedup_key="c" * 64,
            description_ciphertext=credit.description_ciphertext,
        )
        session.add(extra)
        session.flush()
    found = candidates(runtime_engine, owners[0], debit.id)
    requests = [
        PairSelection(
            debit_id=debit.id,
            credit_id=item.entry.id,
            debit_revision=found.source.revision,
            credit_revision=item.entry.revision,
            confirm=True,
        )
        for item in found.candidates
    ]

    def confirm(data):
        try:
            reconcile(runtime_engine, owners[0], data)
            return 200
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(confirm, requests)) == [200, 409]
