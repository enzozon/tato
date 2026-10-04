from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import ValidationError

from app.account_routes import EngineDep, IdentityDep
from app.import_parsers import MAX_FILE_BYTES, CsvMapping, ImportErrorDetail
from app.import_preview import ImportPreview, preview_import
from app.import_service import ImportKind, ImportResult, store_import

router = APIRouter(prefix="/import", tags=["importação"])


@router.post("", response_model=ImportResult)
@router.post("/preview", response_model=ImportPreview)
@router.post("/confirm", response_model=ImportResult)
def upload(
    identity: IdentityDep,
    engine: EngineDep,
    response: Response,
    request: Request,
    account_id: Annotated[UUID, Form()],
    kind: Annotated[ImportKind, Form()],
    file: Annotated[UploadFile, File()],
    mapping: Annotated[str | None, Form(max_length=4096)] = None,
    receipt: Annotated[str | None, Form(max_length=100)] = None,
) -> ImportResult | ImportPreview:
    try:
        if mapping and kind != "csv":
            raise HTTPException(422, "Mapeamento é permitido somente para CSV.")
        columns = CsvMapping.model_validate_json(mapping) if mapping else None
        content = file.file.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(413, "Arquivo maior que 2 MiB.")
        filename = (file.filename or f"arquivo.{kind}").replace("\\", "/").rsplit("/", 1)[-1]
        response.headers["Cache-Control"] = "no-store"
        if request.url.path.endswith("/preview"):
            return preview_import(engine, identity.id, account_id, content, kind, columns)
        if request.url.path.endswith("/confirm"):
            if not receipt:
                raise HTTPException(422, "Revise a prévia antes de confirmar.")
            preview_import(engine, identity.id, account_id, content, kind, columns, receipt)
        result = store_import(engine, identity.id, account_id, content, filename, kind, columns)
    except ImportErrorDetail as error:
        raise HTTPException(422, str(error)) from None
    except ValidationError:
        raise HTTPException(422, "Mapeamento ou lançamentos inválidos.") from None
    except (KeyError, ValueError):
        raise HTTPException(503, "Configuração de importação indisponível.") from None
    finally:
        file.file.close()
    response.headers["Cache-Control"] = "no-store"
    return result
