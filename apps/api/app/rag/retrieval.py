import json
import math
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session

from app.crypto import decrypt_text
from app.rag.ranking import reciprocal_rank_fusion


class Hit(BaseModel):
    chunk_id: UUID
    source: Literal["public", "private"]
    source_id: str
    section: str
    content: str = Field(repr=False)
    score: float = 0


def search(
    session: Session, owner: UUID, query: str, vector: list[float], model: str, key: bytes
) -> list[Hit]:
    if not query.strip() or len(query) > 500 or "\x00" in query:
        raise ValueError("Consulta inválida.")
    if len(vector) != 384 or not all(math.isfinite(v) for v in vector) or not any(vector):
        raise ValueError("Vetor de consulta inválido.")
    params = {"query": query, "vector": json.dumps(vector), "model": model, "owner": owner}
    candidates: dict[str, Hit] = {}
    dense: list[tuple[str, float]] = []
    lexical: list[tuple[str, float]] = []
    for expression, condition, order, ranking in [
        ("embedding <=> CAST(:vector AS vector)", "true", "ASC", dense),
        (
            "ts_rank_cd(search_vector, websearch_to_tsquery('portuguese', :query), 32)",
            "search_vector @@ websearch_to_tsquery('portuguese', :query)",
            "DESC",
            lexical,
        ),
    ]:
        rows = (
            session.execute(
                text(
                    f"SELECT id, slug, section, content, {expression} AS score "
                    "FROM knowledge_chunks "
                    f"WHERE embedding_model=:model AND {condition} "
                    f"ORDER BY score {order}, id LIMIT 20"
                ),
                params,
            )
            .mappings()
            .all()
        )
        for row in rows:
            identifier = f"public:{row['id']}"
            candidates[identifier] = Hit(
                chunk_id=row["id"],
                source="public",
                source_id=row["slug"],
                section=row["section"],
                content=row["content"],
            )
            ranking.append((identifier, float(row["score"])))
    private = (
        session.execute(
            text(
                "SELECT id, document_id, position, content_ciphertext FROM chunks "
                "WHERE user_id=:owner AND embedding_model=:model AND embedding IS NOT NULL "
                "ORDER BY id LIMIT 1001"
            ),
            params,
        )
        .mappings()
        .all()
    )
    if len(private) > 1000:
        raise ValueError("Limite técnico de 1000 chunks privados por usuário excedido.")
    if private:
        logging = session.execute(
            text(
                "SELECT current_setting('log_statement'), "
                "current_setting('log_min_duration_statement'), "
                "current_setting('log_min_duration_sample'), "
                "current_setting('log_parameter_max_length_on_error')"
            )
        ).one()
        if tuple(logging) != ("none", "-1", "-1", "0"):
            raise ValueError("Busca privada exige logs de parâmetros e consultas desativados.")
        payload = []
        for row in private:
            identifier = f"private:{row['id']}"
            content = decrypt_text(row["content_ciphertext"], key, owner, "chunk")
            candidates[identifier] = Hit(
                chunk_id=row["id"],
                source="private",
                source_id=str(row["document_id"]),
                section=f"Trecho {row['position'] + 1}",
                content=content,
            )
            payload.append({"id": str(row["id"]), "content": content})
        rows = (
            session.execute(
                text(
                    "WITH authorized AS MATERIALIZED (SELECT id, embedding FROM chunks "
                    "WHERE user_id=:owner AND embedding_model=:model AND embedding IS NOT NULL) "
                    "SELECT id, embedding <=> CAST(:vector AS vector) AS score FROM authorized "
                    "ORDER BY score, id LIMIT 20"
                ),
                params,
            )
            .mappings()
            .all()
        )
        dense.extend((f"private:{row['id']}", float(row["score"])) for row in rows)
        rows = (
            session.execute(
                text(
                    "WITH authorized AS MATERIALIZED (SELECT id, "
                    "to_tsvector('portuguese', content) AS terms "
                    "FROM jsonb_to_recordset(CAST(:rows AS jsonb)) AS x(id uuid, content text)) "
                    "SELECT id, ts_rank_cd(terms, "
                    "websearch_to_tsquery('portuguese', :query), 32) AS score "
                    "FROM authorized WHERE terms @@ websearch_to_tsquery('portuguese', :query) "
                    "ORDER BY score DESC, id LIMIT 20"
                ),
                {"rows": json.dumps(payload), "query": query},
            )
            .mappings()
            .all()
        )
        lexical.extend((f"private:{row['id']}", float(row["score"])) for row in rows)
    rankings = [
        [key for key, _ in sorted(dense, key=lambda row: (row[1], row[0]))[:20]],
        [key for key, _ in sorted(lexical, key=lambda row: (-row[1], row[0]))[:20]],
    ]
    return [
        candidates[key].model_copy(update={"score": score})
        for key, score in reciprocal_rank_fusion(rankings)
    ]
