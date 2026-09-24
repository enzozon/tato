import os
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError

bearer = HTTPBearer(auto_error=False)


def service_url(name: str) -> str:
    value = os.environ.get(name, "").rstrip("/")
    parsed = urlsplit(value)
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    if (
        not parsed.hostname
        or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(503, "Serviço não configurado.")
    return value


def service_key(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise HTTPException(503, "Serviço não configurado.")
    return value


class Identity(BaseModel):
    id: UUID
    is_anonymous: bool = False


def current_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Identity:
    unauthorized = HTTPException(
        401, "Sessão inválida ou expirada.", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None or len(credentials.credentials) > 8192:
        raise unauthorized
    url = service_url("SUPABASE_URL")
    key = service_key("SUPABASE_PUBLISHABLE_KEY")
    try:
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            response = client.get(
                f"{url}/auth/v1/user",
                headers={"apikey": key, "Authorization": f"Bearer {credentials.credentials}"},
            )
        if response.status_code in {401, 403}:
            raise unauthorized
        response.raise_for_status()
        identity = Identity.model_validate(response.json())
    except (httpx.HTTPError, ValueError, ValidationError):
        raise HTTPException(503, "Autenticação temporariamente indisponível.") from None
    if identity.is_anonymous:
        raise unauthorized
    return identity
