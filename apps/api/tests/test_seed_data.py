from uuid import uuid4

from app.crypto import decrypt_text
from app.models import Chunk, Transaction
from app.seed_data import demo_records


def test_demo_has_stable_ids_and_encrypted_personal_text() -> None:
    owner, key = uuid4(), b"x" * 32
    first, second = demo_records(owner, key, key), demo_records(owner, key, key)
    assert len(first) == 10
    assert [row.id for row in first] == [row.id for row in second]
    transaction = next(row for row in first if isinstance(row, Transaction))
    assert (
        decrypt_text(transaction.description_ciphertext, key, owner, "transaction")
        == "Compra sintética"
    )
    assert next(row for row in first if isinstance(row, Chunk)).embedding is None
