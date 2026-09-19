from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="API financeira", version="0.1.0")


class HealthResponse(BaseModel):
    status: Literal["ok"]


@app.get("/health", response_model=HealthResponse, tags=["saúde"])
def health() -> HealthResponse:
    """Confirma que a API responde; não verifica banco nem provedores."""
    return HealthResponse(status="ok")
