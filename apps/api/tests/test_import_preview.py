from contextlib import nullcontext
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import import_preview as preview

CSV = b"date,title,amount\n2026-09-01,Mercado sintetico,42.00\n"


@pytest.fixture
def ready(monkeypatch):
    monkeypatch.setattr(preview, "authorize_import", lambda *args: None)
    monkeypatch.setattr(preview, "account_session", lambda *args: nullcontext(None))
    monkeypatch.setattr(preview, "active_account", lambda *args: None)
    monkeypatch.setattr(preview, "load_key", lambda *args: b"x" * 32)
    monkeypatch.setattr(preview.time, "time", lambda: 1000)
    return uuid4(), uuid4()


def test_receipt_binds_owner_account_file_and_expiry(ready, monkeypatch):
    owner, account = ready
    result = preview.preview_import(None, owner, account, CSV, "csv", None)
    assert result.debits_cents == 4200 and result.credits_cents == 0 and result.count == 1
    assert preview.preview_import(None, owner, account, CSV, "csv", None, result.receipt) == result
    for user, source, content, receipt in [
        (uuid4(), account, CSV, result.receipt),
        (owner, uuid4(), CSV, result.receipt),
        (owner, account, CSV.replace(b"42.00", b"43.00"), result.receipt),
        (owner, account, CSV, "invalid"),
    ]:
        with pytest.raises(HTTPException) as error:
            preview.preview_import(None, user, source, content, "csv", None, receipt)
        assert error.value.status_code == 409
    monkeypatch.setattr(preview.time, "time", lambda: 1901)
    with pytest.raises(HTTPException):
        preview.preview_import(None, owner, account, CSV, "csv", None, result.receipt)


def test_preview_limits_rows_without_losing_totals(ready):
    content = b"date,title,amount\n" + b"2026-09-01,Sintetico,1.00\n" * 51
    result = preview.preview_import(None, *ready, content, "csv", None)
    assert result.count == 51 and len(result.entries) == 50 and result.truncated
    assert result.debits_cents == 5100
