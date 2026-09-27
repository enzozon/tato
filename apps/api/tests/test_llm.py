import pytest
from pydantic import ValidationError

from app.llm import Generation, MoneyAnswer, verify_money


def test_private_by_default_and_no_payload_in_repr():
    request = Generation(instruction="classifique", data="conteudo privado")
    assert request.classification == "personal"
    assert "privado" not in repr(request)
    with pytest.raises(ValidationError):
        Generation(instruction="a", data="x" * 16001)


def test_schema_does_not_prove_financial_truth():
    answer = MoneyAnswer(source_id="sql:total", amount_cents=4200)
    assert verify_money(answer, {"sql:total": 4200})
    assert not verify_money(answer, {"sql:total": 4300})
    assert not verify_money(answer, {"another": 4200})
    with pytest.raises(ValidationError):
        MoneyAnswer(source_id="sql:total", amount_cents=42.5)
