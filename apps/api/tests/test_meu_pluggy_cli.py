import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.import_parsers import parse_csv

spec = importlib.util.spec_from_file_location("meu_pluggy_cli", Path("scripts/meu_pluggy.py"))
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
CLIENT = httpx.Client
ARGS = ["--from", "2026-10-10", "--to", "2026-10-10"]


@pytest.fixture(autouse=True)
def configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "OUTPUT", tmp_path / "test-results" / "meu-pluggy")
    for key in cli.VARIABLES:
        monkeypatch.setenv(key, "private-canary")


def test_opt_in_configuration_and_period_before_network(monkeypatch, capsys):
    monkeypatch.setattr(cli.httpx, "Client", lambda **_: pytest.fail("Sem rede"))
    assert cli.main(ARGS) == 2
    assert cli.main(["--confirm-personal-use", "--from", "2026-10-11", "--to", "2026-10-10"]) == 1
    assert cli.main(["--confirm-personal-use", "--from", "9999-12-29", "--to", "9999-12-30"]) == 1
    monkeypatch.delenv(cli.VARIABLES[0])
    assert cli.main([*ARGS, "--confirm-personal-use"]) == 1
    message = capsys.readouterr().out
    assert cli.VARIABLES[0] in message
    assert "MEU_PLUGGY_CLIENT_SECRET" not in message and "private-canary" not in message


def test_snapshot_selection_export_and_no_overwrite(monkeypatch, capsys):
    monkeypatch.setenv("MEU_PLUGGY_ACCOUNT_ID", "account-private")

    def respond(request):
        if request.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "private-canary"})
        if request.url.path == "/accounts":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "account-private",
                            "itemId": "private-canary",
                            "type": "BANK",
                            "subtype": "CHECKING_ACCOUNT",
                            "currencyCode": "BRL",
                            "name": "private-canary",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "txn-private",
                        "accountId": "account-private",
                        "date": "2026-10-10T12:00:00Z",
                        "amount": -1.23,
                        "type": "DEBIT",
                        "status": "POSTED",
                        "currencyCode": "BRL",
                        "description": "private-canary",
                    }
                ],
                "next": None,
            },
        )

    monkeypatch.setattr(
        cli.httpx,
        "Client",
        lambda **kwargs: CLIENT(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(cli, "uuid4", lambda: SimpleNamespace(hex="synthetic"))
    assert cli.main([*ARGS, "--confirm-personal-use"]) == 0
    files = list(cli.OUTPUT.glob("*.csv"))
    assert len(files) == 1 and parse_csv(files[0].read_bytes())[0].amount_cents == -123
    original = files[0].read_bytes()
    message = capsys.readouterr().out
    assert "conta-synthetic.csv" in message and "private-canary" not in message
    assert cli.main([*ARGS, "--confirm-personal-use"]) == 1
    assert files[0].read_bytes() == original and not list(cli.OUTPUT.glob("*.tmp"))
    assert "private-canary" not in capsys.readouterr().out


def test_atomic_write_failure_removes_temporary(monkeypatch):
    monkeypatch.setattr(cli.os, "link", lambda *_: (_ for _ in ()).throw(OSError("private-canary")))
    with pytest.raises(OSError):
        cli.save_csv(b"synthetic")
    assert not list(cli.OUTPUT.iterdir())


def test_refuses_output_outside_project(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "OUTPUT", tmp_path.parent / "outside")
    with pytest.raises(ValueError):
        cli.save_csv(b"synthetic")


def test_wrong_account_never_requests_transactions(monkeypatch, capsys):
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.path in {"/auth", "/accounts"}
        return httpx.Response(
            200,
            json={"apiKey": "key"}
            if request.url.path == "/auth"
            else {
                "results": [
                    {
                        "id": "other",
                        "itemId": "private-canary",
                        "type": "BANK",
                        "subtype": "CHECKING_ACCOUNT",
                        "currencyCode": "BRL",
                    }
                ]
            },
        )

    monkeypatch.setattr(
        cli.httpx,
        "Client",
        lambda **kwargs: CLIENT(transport=httpx.MockTransport(respond), **kwargs),
    )
    assert cli.main([*ARGS, "--confirm-personal-use"]) == 1
    assert len(calls) == 2 and not cli.OUTPUT.exists()
    assert "private-canary" not in capsys.readouterr().out
