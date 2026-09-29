from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.rag.retrieval import search


def result(rows):
    return Mock(mappings=lambda: Mock(all=lambda: rows))


def test_public_rankings_fuse_and_private_query_is_scoped():
    owner, identifier = uuid4(), uuid4()
    session = Mock()
    row = {
        "id": identifier,
        "slug": "reserva",
        "section": "Reserva",
        "content": "Imprevistos",
        "score": 0.2,
    }
    session.execute.side_effect = [
        Mock(one=lambda: ("none", "-1", "-1", "0")),
        result([row]),
        result([row]),
        result([]),
    ]
    hits = search(session, owner, "reserva", [1.0] + [0.0] * 383, "test", b"x" * 32)
    assert len(hits) == 1 and hits[0].chunk_id == identifier
    assert hits[0].score == 2 / 61
    query, parameters = session.execute.call_args.args
    assert "user_id=:owner" in str(query) and parameters["owner"] == owner


def test_invalid_input_cannot_reach_sql():
    session = Mock()
    with pytest.raises(ValueError):
        search(session, uuid4(), "x", [float("nan")] * 384, "test", b"x" * 32)
    session.execute.assert_not_called()


def test_unsafe_logging_blocks_question_before_any_parameter_is_sent():
    session = Mock()
    session.execute.return_value.one.return_value = ("all", "-1", "-1", "0")
    question = "descrição financeira privada"
    with pytest.raises(ValueError, match="logs"):
        search(session, uuid4(), question, [1.0] + [0.0] * 383, "test", b"x" * 32)
    assert session.execute.call_count == 1
    args = session.execute.call_args.args
    assert len(args) == 1 and question not in str(args[0])
