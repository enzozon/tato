from datetime import date

import pytest

from app.account_service import account_session
from app.crypto import encrypt_text
from app.dashboard import summary
from app.models import Account, Transaction
from tests.integration.test_agent_config import agent_accounts as agent_accounts

pytestmark = pytest.mark.integration


def test_summary_preserves_money_and_owner(runtime_engine, owners, agent_accounts, monkeypatch):
    monkeypatch.setattr("app.dashboard.check_rate", lambda *args: None)
    for owner, account_id in zip(owners, agent_accounts, strict=True):
        with account_session(runtime_engine, owner) as session:
            account = session.get(Account, account_id)
            account.name_ciphertext = encrypt_text("Conta sintética", b"x" * 32, owner, "account")
            account.opening_balance_cents = 2**60
            session.add(account)
    with account_session(runtime_engine, owners[0]) as session:
        for day, amount in [(date(2026, 10, 2), -101), (date(2026, 11, 1), -999)]:
            session.add(
                Transaction(
                    user_id=owners[0],
                    account_id=agent_accounts[0],
                    booked_on=day,
                    amount_cents=amount,
                    kind="expense",
                    description_ciphertext=b"test",
                    dedup_key=str(day.day) * 64,
                )
            )
    result = summary(runtime_engine, owners[0], date(2026, 10, 4))
    assert result.balance_cents == str(2**60 - 101)
    assert result.expense_cents == "101" and result.categories[0].name == "Sem categoria"
    other = summary(runtime_engine, owners[1], date(2026, 10, 4))
    assert other.expense_cents == "0" and len(other.accounts) == 1
