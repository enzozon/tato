import os
from collections.abc import Callable
from contextlib import suppress
from functools import lru_cache
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine
from sqlmodel import Session

from app import llm_cache
from app.account_service import account_session
from app.llm import Generation, LLMProvider, LLMUnavailable, ProviderName
from app.llm_http import HTTPProvider
from app.llm_policy import personal_allowed
from app.llm_router import Routed, Router
from app.models import User


@lru_cache(maxsize=1)
def runtime_router() -> Router:
    if os.environ.get("LLM_ENABLED") != "true":
        return Router([])
    if os.environ.get("LLM_FREE_TIER_CONFIRMED") != "true":
        raise LLMUnavailable("Confirme contas sem faturamento antes de habilitar LLM.")
    providers: list[LLMProvider] = []
    settings: tuple[tuple[ProviderName, str], ...] = (
        ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-2.5-flash"),
        ("openrouter", os.environ.get("OPENROUTER_MODEL", "")),
    )
    client = httpx.Client(timeout=10, follow_redirects=False, trust_env=False)
    for name, model in settings:
        key = os.environ.get(f"{name.upper()}_API_KEY", "").strip()
        if key and model:
            providers.append(HTTPProvider(name, model, key, client))
    if not providers:
        client.close()
    return Router(providers)


def require_active(session: Session, owner: UUID) -> None:
    user = session.get(User, owner)
    if user is None or user.deletion_requested_at is not None:
        raise LLMUnavailable("Conta ausente ou com exclusão pendente.")


def generate[T: BaseModel](
    engine: Engine, owner: UUID, request: Generation, output: type[T], guard: Callable[[T], bool]
) -> Routed[T]:
    if request.classification == "personal" and not personal_allowed("groq"):
        raise LLMUnavailable("Dados pessoais ainda não habilitados para provedores.")
    router = runtime_router()
    mode = os.environ.get("LLM_CACHE", "off")
    if mode not in {"off", "redis"}:
        raise LLMUnavailable("Cache não configurado corretamente.")
    field = llm_cache.fingerprint(request, output, router.providers) if mode == "redis" else ""
    with account_session(engine, owner) as session:
        require_active(session, owner)
        if mode == "redis":
            try:
                cached = llm_cache.get_cached(owner, field)
                if cached is not None:
                    value = output.model_validate_json(cached, strict=True)
                    if guard(value):
                        return Routed(value, (), cached=True)
            except (HTTPException, ValueError, ValidationError):
                pass  # Cache indisponível não transforma falha de Redis em quota ilimitada.
    result = router.generate(request, output, guard)
    with account_session(engine, owner) as session:
        # A exclusão pode ter começado enquanto o provedor respondia.
        require_active(session, owner)
        if mode == "redis":
            with suppress(HTTPException, ValueError):
                llm_cache.put_cached(owner, field, result.value.model_dump_json())
    return result
