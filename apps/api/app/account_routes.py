import os
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine

from app.account_service import Profile, profile, request_deletion
from app.auth import Identity, bearer, current_identity
from app.database import app_engine

router = APIRouter(prefix="/me", tags=["conta"])


@lru_cache(maxsize=1)
def runtime_engine() -> Engine:
    try:
        return app_engine(os.environ["DATABASE_URL"])
    except (KeyError, ValueError):
        raise HTTPException(503, "Banco não configurado.") from None


class OnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    completed: Literal[True]


IdentityDep = Annotated[Identity, Depends(current_identity)]
EngineDep = Annotated[Engine, Depends(runtime_engine)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


@router.get("", response_model=Profile)
def get_me(
    identity: IdentityDep, engine: EngineDep, credentials: CredentialsDep, response: Response
) -> Profile:
    response.headers["Cache-Control"] = "no-store"
    return profile(engine, identity.id, lambda: current_identity(credentials))


@router.post("/onboarding", response_model=Profile)
def complete_onboarding(
    data: OnboardingInput,
    identity: IdentityDep,
    engine: EngineDep,
    credentials: CredentialsDep,
    response: Response,
) -> Profile:
    response.headers["Cache-Control"] = "no-store"
    return profile(engine, identity.id, lambda: current_identity(credentials), complete=True)


class DeletionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirm: Literal[True]


@router.delete("", status_code=204)
def delete_me(
    data: DeletionInput, identity: IdentityDep, engine: EngineDep, credentials: CredentialsDep
) -> Response:
    request_deletion(engine, identity.id, lambda: current_identity(credentials))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
