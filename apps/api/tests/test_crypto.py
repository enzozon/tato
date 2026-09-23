import base64
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag

from app.crypto import decrypt_text, dedup_key, encrypt_text, load_key


def test_authenticated_encryption_rejects_tampering_and_foreign_context() -> None:
    key, owner = b"x" * 32, uuid4()
    first = encrypt_text("Mercado sintético R$ 42", key, owner, "description")
    second = encrypt_text("Mercado sintético R$ 42", key, owner, "description")
    assert first != second
    assert b"Mercado" not in first
    assert decrypt_text(first, key, owner, "description") == "Mercado sintético R$ 42"
    for ciphertext, secret, user, purpose in [
        (first[:-1] + bytes([first[-1] ^ 1]), key, owner, "description"),
        (first, b"y" * 32, owner, "description"),
        (first, key, uuid4(), "description"),
        (first, key, owner, "goal"),
    ]:
        with pytest.raises(InvalidTag):
            decrypt_text(ciphertext, secret, user, purpose)
    with pytest.raises(ValueError):
        encrypt_text("texto", b"x" * 16, owner, "description")
    with pytest.raises(ValueError):
        decrypt_text(first, b"x" * 16, owner, "description")


def test_dedup_uses_operation_identity_and_owner() -> None:
    key, owner, account = b"x" * 32, uuid4(), uuid4()
    first = dedup_key(key, owner, account, "ofx:123")
    assert first == dedup_key(key, owner, account, "ofx:123")
    assert len(first) == 64
    assert first != dedup_key(key, owner, account, "ofx:124")
    assert first != dedup_key(key, uuid4(), account, "ofx:123")
    assert first != dedup_key(key, owner, uuid4(), "ofx:123")
    with pytest.raises(ValueError):
        dedup_key(key, owner, account, " ")


def test_key_loading_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TATO_TEST_KEY", base64.b64encode(b"x" * 32).decode())
    assert load_key("TATO_TEST_KEY") == b"x" * 32
    monkeypatch.setenv("TATO_TEST_KEY", "cGVxdWVubw==")
    with pytest.raises(ValueError):
        load_key("TATO_TEST_KEY")
    monkeypatch.delenv("TATO_TEST_KEY")
    with pytest.raises(KeyError):
        load_key("TATO_TEST_KEY")
