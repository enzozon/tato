import os
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.account_routes import router
from app.agent_routes import router as agent_router
from app.chat_routes import router as chat_router
from app.dashboard import router as dashboard_router
from app.import_routes import router as import_router
from app.import_setup import router as setup_router
from app.rag.routes import router as rag_router
from app.upload_limit import UploadLimit
from app.usage import router as usage_router

app = FastAPI(title="API financeira", version="0.1.0")
app.include_router(router)
app.include_router(agent_router)
app.include_router(import_router)
app.include_router(setup_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(usage_router)
app.add_middleware(UploadLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "WEB_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"
    ).split(","),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(SQLAlchemyError)
@app.exception_handler(PermissionError)
async def storage_unavailable(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Armazenamento temporariamente indisponível."},
        headers={"Cache-Control": "no-store"},
    )


class HealthResponse(BaseModel):
    status: Literal["ok"]


@app.get("/health", response_model=HealthResponse, tags=["saúde"])
def health() -> HealthResponse:
    """Confirma que a API responde; não verifica banco nem provedores."""
    return HealthResponse(status="ok")
