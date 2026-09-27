from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.account_routes import router
from app.import_routes import router as import_router
from app.upload_limit import UploadLimit

app = FastAPI(title="API financeira", version="0.1.0")
app.include_router(router)
app.include_router(import_router)
app.add_middleware(UploadLimit)


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
