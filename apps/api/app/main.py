from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.account_routes import router

app = FastAPI(title="API financeira", version="0.1.0")
app.include_router(router)


class HealthResponse(BaseModel):
    status: Literal["ok"]


@app.get("/health", response_model=HealthResponse, tags=["saúde"])
def health() -> HealthResponse:
    """Confirma que a API responde; não verifica banco nem provedores."""
    return HealthResponse(status="ok")
