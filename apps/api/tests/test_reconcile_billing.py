import importlib.util
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.billing_stripe import BillingUnavailable


@pytest.fixture
def command():
    path = Path(__file__).resolve().parents[3] / "scripts/reconcile_billing.py"
    spec = importlib.util.spec_from_file_location("reconcile_billing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reconcile_requires_explicit_opt_in_before_any_provider_or_database(command, monkeypatch):
    engine = Mock()
    monkeypatch.setattr(command, "billing_engine", engine)
    with pytest.raises(SystemExit) as error:
        command.main(["--owner", str(uuid4()), "--request-id", str(uuid4())])
    assert error.value.code == 2
    engine.assert_not_called()


def test_reconcile_uses_typed_ids_and_sanitizes_provider_failure(command, monkeypatch, capsys):
    owner, request_id = uuid4(), uuid4()
    monkeypatch.setattr(command, "billing_engine", lambda: None)
    monkeypatch.setattr(command, "provider_for", lambda client: None)
    function = Mock()
    monkeypatch.setattr(command, "reconcile", function)
    args = ["--owner", str(owner), "--request-id", str(request_id), "--confirm-sandbox"]
    command.main(args)
    function.assert_called_once_with(None, None, owner, request_id)
    assert str(owner) not in capsys.readouterr().out
    function.side_effect = BillingUnavailable("private-provider-data")
    with pytest.raises(SystemExit) as error:
        command.main(args)
    assert "private" not in str(error.value)
