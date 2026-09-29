import hashlib
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Engine, delete, func
from sqlmodel import Session, col, select

from app.account_service import account_session
from app.crypto import decrypt_text, encrypt_text, load_key
from app.models import Chunk, Document, KnowledgeChunk, User
from app.rag.chunking import TextChunk, chunk_markdown
from app.rag.embedding import embed, encoder


def prepare(content: str) -> tuple[list[TextChunk], list[list[float]], str]:
    _, tokenizer, model = encoder()
    chunks = chunk_markdown(content, tokenizer)
    vectors = []
    for offset in range(0, len(chunks), 64):
        vectors.extend(embed([chunk.text for chunk in chunks[offset : offset + 64]]))
    return chunks, vectors, model


def index_public(engine: Engine, slug: str, content: str) -> int:
    if not slug or len(slug) > 160:
        raise ValueError("Identificador público inválido.")
    chunks, vectors, model = prepare(content)
    if not chunks:
        raise ValueError("Documento público vazio.")
    with Session(engine) as session, session.begin():
        session.execute(delete(KnowledgeChunk).where(col(KnowledgeChunk.slug) == slug))
        for position, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            session.add(
                KnowledgeChunk(
                    id=uuid5(NAMESPACE_URL, f"tato:knowledge:{slug}:{position}"),
                    slug=slug,
                    position=position,
                    section=chunk.section,
                    content=chunk.text,
                    content_digest=hashlib.sha256(chunk.text.encode()).hexdigest(),
                    embedding=vector,
                    embedding_model=model,
                )
            )
    return len(chunks)


def require_document(session: Session, owner: UUID, identifier: UUID) -> Document:
    user, document = session.get(User, owner), session.get(Document, identifier)
    if user is None or user.deletion_requested_at is not None:
        raise ValueError("Conta ausente ou com exclusão pendente.")
    if document is None or document.user_id != owner:
        raise ValueError("Documento não encontrado.")
    if document.kind not in {"pdf", "note", "summary"}:
        raise ValueError("Transações CSV/OFX pertencem à análise SQL, não ao RAG.")
    return document


def index_private(engine: Engine, owner: UUID, identifier: UUID) -> int:
    key = load_key("DATA_ENCRYPTION_KEY")
    with account_session(engine, owner) as session:
        document = require_document(session, owner, identifier)
        digest = document.digest
        content = decrypt_text(document.content_ciphertext, key, owner, "document")
    chunks, vectors, model = prepare(content)
    with account_session(engine, owner) as session:
        document = require_document(session, owner, identifier)
        if document.digest != digest:
            raise ValueError("Documento mudou durante a indexação; tente novamente.")
        existing = session.scalar(
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.user_id == owner, Chunk.document_id != identifier)
        )
        if int(existing or 0) + len(chunks) > 1000:
            raise ValueError("Limite técnico de 1000 chunks privados atingido.")
        session.execute(
            delete(Chunk).where(col(Chunk.user_id) == owner, col(Chunk.document_id) == identifier)
        )
        for position, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            session.add(
                Chunk(
                    id=uuid5(identifier, str(position)),
                    user_id=owner,
                    document_id=identifier,
                    position=position,
                    content_ciphertext=encrypt_text(chunk.text, key, owner, "chunk"),
                    embedding=vector,
                    embedding_model=model,
                )
            )
    return len(chunks)
