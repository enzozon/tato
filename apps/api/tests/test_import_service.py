from contextlib import contextmanager
from datetime import date
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import import_service as service
from app.import_parsers import ParsedEntry
from app.models import Account, User
from app.plans import FREE


def test_active_account_rejects_cross_tenant():
    owner, other, account = uuid4(), uuid4(), uuid4()
    session = Mock()
    session.get.side_effect = [User(id=owner), Account(id=account, user_id=other)]
    with pytest.raises(HTTPException) as error:
        service.active_account(session, owner, account)
    assert error.value.status_code == 404


@pytest.mark.parametrize("repeat", [False, True])
def test_import_counts_and_document_context(monkeypatch, repeat):
    owner, account = uuid4(), uuid4()
    session = Mock()
    session.exec.side_effect = (
        [Mock(first=lambda: Mock(id=uuid4()))]
        if repeat
        else [
            Mock(first=lambda: None),
            Mock(all=lambda: []),
            Mock(all=lambda: []),
        ]
    )
    session.scalar.return_value = 0

    @contextmanager
    def transaction(*args):
        yield session

    monkeypatch.setattr(service, "account_session", transaction)
    monkeypatch.setattr(service, "authorize_import", lambda *args: None)
    monkeypatch.setattr(service, "active_account", lambda *args: None)
    monkeypatch.setattr(service, "user_plan", lambda *args: FREE)
    monkeypatch.setattr(service, "load_key", lambda *args: b"x" * 32)
    monkeypatch.setattr(service, "load_rules", lambda *args: [])
    monkeypatch.setattr(
        service,
        "parse_upload",
        lambda *args: (
            "private",
            [
                ParsedEntry(
                    booked_on=date(2026, 9, 1),
                    amount_cents=-4200,
                    description="private",
                    source_identity="csv:1",
                )
            ],
        ),
    )
    inserted = Mock(return_value=uuid4())
    monkeypatch.setattr(service, "add_transaction", inserted)
    result = service.store_import(Mock(), owner, account, b"synthetic", "file.csv", "csv")
    assert result.inserted == int(not repeat)
    assert result.duplicates == int(repeat)
    assert "private" not in result.model_dump_json()
    if not repeat:
        assert inserted.call_args.kwargs["document_id"] == result.document_id
