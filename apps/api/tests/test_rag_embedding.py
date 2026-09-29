from unittest.mock import Mock

import numpy as np
import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import WhitespaceSplit

from app.rag import embedding


def test_prefixes_limits_and_dimensions(monkeypatch):
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = WhitespaceSplit()
    model = Mock()
    model.embed.return_value = [np.array([1.0] + [0.0] * 383)]
    monkeypatch.setattr(embedding, "encoder", lambda: (model, tokenizer, "test"))
    assert len(embedding.embed(["reserva"], query=True)[0]) == 384
    assert model.embed.call_args.args[0] == ["query: reserva"]
    embedding.embed(["texto público"])
    assert model.embed.call_args.args[0] == ["passage: texto público"]
    with pytest.raises(ValueError, match="janela"):
        embedding.embed(["palavra " * 512])
    with pytest.raises(ValueError):
        embedding.embed([])
    model.embed.return_value = [np.zeros(384)]
    with pytest.raises(ValueError, match="inválido"):
        embedding.embed(["texto"])
