import json
import re
from pathlib import Path


def test_public_corpus_has_independent_identifiable_documents():
    path = Path(__file__).resolve().parents[3] / "knowledge/base.jsonl"
    documents = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(documents) == 200
    assert len({item["slug"] for item in documents}) == 200
    assert len({item["text"] for item in documents}) == 200
    for item in documents:
        assert set(item) == {"slug", "title", "text"}
        assert re.fullmatch(r"[a-z0-9-]{1,160}", item["slug"])
        assert 1 <= len(item["title"]) <= 200
        assert 100 <= len(item["text"]) <= 2000
