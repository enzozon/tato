import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import WhitespaceSplit

from app.rag.chunking import chunk_markdown


@pytest.fixture
def tokenizer():
    instance = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    instance.pre_tokenizer = WhitespaceSplit()
    return instance


def test_sections_and_sentence_boundaries(tokenizer):
    result = chunk_markdown(
        "# Reserva\nDinheiro para imprevistos.\n# Meta\nObjetivo definido.", tokenizer
    )
    assert [chunk.section for chunk in result] == ["Reserva", "Meta"]
    assert result[0].text == "Dinheiro para imprevistos."
    assert result[1].text == "Objetivo definido."


def test_long_sentence_preserves_words_and_overlaps(tokenizer):
    words = [f"palavra{i}" for i in range(100)]
    result = chunk_markdown(" ".join(words), tokenizer, target=40)
    assert all(chunk.tokens <= 40 for chunk in result)
    assert result[0].text.split()[-6:] == result[1].text.split()[:6]
    assert set(" ".join(chunk.text for chunk in result).split()) == set(words)


def test_no_hidden_truncation_empty_and_limits(tokenizer):
    assert chunk_markdown("# Vazio", tokenizer) == []
    with pytest.raises(ValueError):
        chunk_markdown("x" * 200001, tokenizer)
    tokenizer.enable_truncation(10)
    with pytest.raises(ValueError, match="truncamento"):
        chunk_markdown("texto", tokenizer)
