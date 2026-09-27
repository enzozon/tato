"""Extração textual limitada; executada em processo separado, sem credenciais."""

import io
import logging
import os
import subprocess
import sys
from pathlib import Path

from app.import_parsers import MAX_FILE_BYTES, ImportErrorDetail

MAX_TEXT = 200_000


def extract_pdf(content: bytes) -> str:
    if not content.startswith(b"%PDF-") or len(content) > MAX_FILE_BYTES:
        raise ImportErrorDetail("PDF inválido ou maior que 2 MiB.")
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.pdf_extract"],
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        raise ImportErrorDetail("PDF excedeu o tempo de extração.") from None
    if result.returncode or not result.stdout or len(result.stdout) > MAX_TEXT * 4:
        raise ImportErrorDetail("PDF sem texto, protegido, inválido ou acima dos limites.")
    return result.stdout.decode("utf-8")


def worker(content: bytes) -> str:
    import pypdf.filters as filters
    from pypdf import PdfReader

    logging.disable(logging.CRITICAL)
    filters.ZLIB_MAX_OUTPUT_LENGTH = 8 * 1024 * 1024
    filters.LZW_MAX_OUTPUT_LENGTH = 8 * 1024 * 1024
    filters.RUN_LENGTH_MAX_OUTPUT_LENGTH = 8 * 1024 * 1024
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted or len(reader.pages) > 40:
        raise ValueError("PDF não permitido.")
    result = ""
    for page in reader.pages:
        stream = page.get_contents()
        if stream is not None and len(stream.get_data()) > 8 * 1024 * 1024:
            raise ValueError("Página excessiva.")
        result += (page.extract_text() or "") + "\n"
        if len(result) > MAX_TEXT:
            raise ValueError("Texto excessivo.")
    return result.strip()


if __name__ == "__main__":
    try:
        raw = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("Arquivo excessivo.")
        sys.stdout.buffer.write(worker(raw).encode("utf-8"))
    except Exception:
        # O pai recebe só status; não imprimir trecho privado nem traceback do parser.
        sys.exit(1)
