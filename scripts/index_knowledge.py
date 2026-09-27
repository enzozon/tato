"""Indexa somente a base pública versionada usando a conexão administrativa."""

import json
import os
from pathlib import Path

from app.database import app_engine
from app.rag.indexing import index_public


def main() -> None:
    path = Path(__file__).resolve().parents[1] / "knowledge/base.jsonl"
    documents = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    engine = app_engine(os.environ["DATABASE_MIGRATION_URL"])
    try:
        chunks = sum(
            index_public(engine, item["slug"], f"# {item['title']}\n\n{item['text']}")
            for item in documents
        )
        print(json.dumps({"documents": len(documents), "chunks": chunks}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
