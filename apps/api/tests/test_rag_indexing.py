from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.models import Document, User
from app.rag import indexing


def test_document_gate_rejects_cross_tenant_and_transactions():
    owner, other, identifier = uuid4(), uuid4(), uuid4()
    session = Mock()
    session.get.side_effect = [User(id=owner), Document(id=identifier, user_id=other, kind="note")]
    with pytest.raises(ValueError, match="não encontrado"):
        indexing.require_document(session, owner, identifier)
    session.get.side_effect = [User(id=owner), Document(id=identifier, user_id=owner, kind="csv")]
    with pytest.raises(ValueError, match="SQL"):
        indexing.require_document(session, owner, identifier)


def test_prepare_batches_without_dropping_chunks(monkeypatch):
    chunks = [Mock(text=f"text{i}") for i in range(65)]
    monkeypatch.setattr(indexing, "encoder", lambda: (None, None, "model"))
    monkeypatch.setattr(indexing, "chunk_markdown", lambda *args: chunks)
    encode = Mock(side_effect=lambda texts: [[1.0]] * len(texts))
    monkeypatch.setattr(indexing, "embed", encode)
    result, vectors, model = indexing.prepare("synthetic")
    assert len(result) == len(vectors) == 65 and model == "model"
    assert [len(call.args[0]) for call in encode.call_args_list] == [64, 1]
