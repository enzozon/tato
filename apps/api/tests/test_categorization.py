from unittest.mock import Mock
from uuid import uuid4

from app.categorization import load_rules, match_category
from app.crypto import encrypt_text
from app.models import Rule


def test_rules_are_literal_ordered_and_tenant_bound():
    owner, first, second = uuid4(), uuid4(), uuid4()
    key = b"s" * 32
    rule = Rule(
        user_id=owner,
        category_id=first,
        pattern_ciphertext=encrypt_text("MERCÁDO", key, owner, "rule"),
    )
    session = Mock()
    session.exec.return_value.all.return_value = [rule]
    rules = load_rules(session, owner, key)
    assert owner in session.exec.call_args.args[0].compile().params.values()
    assert match_category("Compra no mercado", rules + [("compra", second)]) == first
    assert match_category("Sem correspondência", rules) is None
    assert match_category("qualquer texto", [(".*", first), ("", second)]) is None
