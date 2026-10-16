import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session, select

from app import categorization_llm, import_service
from app.crypto import decrypt_text, encrypt_text, load_key
from app.database import tenant_session
from app.llm_router import Routed
from app.models import Category, Document, Rule, Transaction, User
from tests.integration.test_import import CSV
from tests.integration.test_import import accounts as accounts

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("change", ["none", "rename", "rule", "deletion"])
def test_confirm_revalidates_after_unlocked_inference(
    runtime_engine, admin_engine, owners, accounts, monkeypatch, change
):
    owner, account = owners[0], accounts[0]
    with tenant_session(runtime_engine, owner) as session:
        category = Category(user_id=owner, name="Mercado sintético")
        local = Category(user_id=owner, name="Regra sintética")
        session.add_all([category, local])
        session.flush()
        category_id, rule_id = category.id, local.id
    calls = []
    monkeypatch.setattr(categorization_llm, "personal_allowed", lambda provider: True)

    def generate(engine, user, request, schema, guard):
        # Uma segunda sessão deve obter o lock durante a inferência.
        with import_service.account_session(runtime_engine, owner) as session:
            if change == "rename":
                row = session.get(Category, category_id)
                row.name = "Categoria alterada"
                session.add(row)
            elif change == "rule":
                session.add(
                    Rule(
                        user_id=owner,
                        category_id=rule_id,
                        pattern_ciphertext=encrypt_text(
                            "mercado", load_key("DATA_ENCRYPTION_KEY"), owner, "rule"
                        ),
                    )
                )
        if change == "deletion":
            with Session(admin_engine) as session, session.begin():
                session.exec(
                    update(User)
                    .where(User.id == owner)
                    .values(deletion_requested_at=datetime.now(UTC))
                )
        calls.append(request)
        assert user == owner
        payload = json.loads(request.data)
        assert {item["id"] for item in payload["categories"]} == {str(category_id), str(rule_id)}
        assert all(set(item) == {"entry_index", "description"} for item in payload["entries"])
        result = schema.model_validate_json(
            json.dumps(
                {
                    "choices": [
                        {"entry_index": item["entry_index"], "category_id": str(category_id)}
                        for item in payload["entries"]
                    ]
                }
            )
        )
        assert guard(result)
        return Routed(result, ())

    monkeypatch.setattr(categorization_llm, "generate", generate)
    if change == "deletion":
        with pytest.raises(HTTPException) as error:
            import_service.store_import(
                runtime_engine, owner, account, CSV, "x.csv", "csv", categorize=True
            )
        assert error.value.status_code == 409
        with tenant_session(runtime_engine, owner) as session:
            assert not session.exec(select(Transaction)).all()
            assert not session.exec(select(Document)).all()
        return
    result = import_service.store_import(
        runtime_engine, owner, account, CSV, "x.csv", "csv", categorize=True
    )
    assert result.inserted == 2 and len(calls) == 1
    with tenant_session(runtime_engine, owner) as session:
        rows = session.exec(select(Transaction)).all()
        expected = None if change == "rename" else rule_id if change == "rule" else category_id
        assert {row.category_id for row in rows} == {expected}
        assert {row.amount_cents for row in rows} == {-4200}
        assert {
            decrypt_text(
                row.description_ciphertext, load_key("DATA_ENCRYPTION_KEY"), owner, "transaction"
            )
            for row in rows
        } == {"Mercado sintetico"}
    replay = import_service.store_import(
        runtime_engine, owner, account, CSV, "x.csv", "csv", categorize=True
    )
    assert replay.inserted == 0 and replay.duplicates == 2 and len(calls) == 1
    with pytest.raises(HTTPException) as error:
        import_service.store_import(
            runtime_engine, owners[1], account, CSV, "x.csv", "csv", categorize=True
        )
    assert error.value.status_code == 404 and len(calls) == 1
