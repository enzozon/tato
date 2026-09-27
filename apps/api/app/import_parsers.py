import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000


class ImportErrorDetail(ValueError):
    """Mensagem pública sem reproduzir conteúdo financeiro do arquivo."""


class ParsedEntry(BaseModel):
    booked_on: date
    amount_cents: int = Field(ge=-(2**63), le=2**63 - 1)
    description: str = Field(min_length=1, max_length=5000)
    source_identity: str = Field(max_length=200)
    kind: Literal["income", "expense", "transfer"] | None = None


class CsvMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date_column: str = Field(min_length=1, max_length=100)
    description_column: str = Field(min_length=1, max_length=100)
    amount_column: str = Field(min_length=1, max_length=100)
    id_column: str | None = Field(default=None, max_length=100)
    decimal_separator: Literal[".", ","] = ","
    debit_positive: bool = False


def decode_file(content: bytes) -> str:
    if not content or len(content) > MAX_FILE_BYTES:
        raise ImportErrorDetail("Arquivo vazio ou maior que 2 MiB.")
    try:
        result = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            result = content.decode("cp1252", errors="strict")
        except UnicodeDecodeError:
            raise ImportErrorDetail("Codificação não reconhecida.") from None
    if "\x00" in result:
        raise ImportErrorDetail("Arquivo textual inválido.")
    return result


def parse_money(value: str, separator: str) -> int:
    value = value.strip()
    if len(value) > 32 or separator not in {".", ","}:
        raise ImportErrorDetail("Formato monetário inválido.")
    decimal = re.escape(separator)
    thousands = r"\." if separator == "," else ","
    if not re.fullmatch(
        rf"[+-]?(?:\d+|\d{{1,3}}(?:{thousands}\d{{3}})+)(?:{decimal}\d{{1,2}})?", value
    ):
        raise ImportErrorDetail("Valor monetário inválido ou precisão maior que centavos.")
    normalized = value.replace("." if separator == "," else ",", "").replace(separator, ".")
    cents = int(Decimal(normalized) * 100)
    if cents == 0 or not -(2**63) <= cents <= 2**63 - 1:
        raise ImportErrorDetail("Valor zero ou fora do intervalo permitido.")
    return cents


def parse_date(value: str) -> date:
    for layout in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), layout).date()
        except ValueError:
            pass
    raise ImportErrorDetail("Data inválida; use AAAA-MM-DD ou DD/MM/AAAA.")


def detect_csv(columns: list[str]) -> CsvMapping:
    if set(columns) == {"date", "title", "amount"}:
        return CsvMapping(
            date_column="date",
            description_column="title",
            amount_column="amount",
            decimal_separator=".",
            debit_positive=True,
        )
    if {"Data", "Valor", "Identificador", "Descrição"} <= set(columns):
        return CsvMapping(
            date_column="Data",
            amount_column="Valor",
            id_column="Identificador",
            description_column="Descrição",
            decimal_separator=",",
        )
    raise ImportErrorDetail("Layout não reconhecido; informe o mapeamento de colunas.")


def parse_csv(content: bytes, mapping: CsvMapping | None = None) -> list[ParsedEntry]:
    text = decode_file(content)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect, strict=True)
        columns = list(reader.fieldnames or [])
        if not columns or len(columns) != len(set(columns)) or any(len(c) > 100 for c in columns):
            raise ImportErrorDetail("Cabeçalho ausente ou duplicado.")
        mapping = mapping or detect_csv(columns)
        required = [mapping.date_column, mapping.description_column, mapping.amount_column]
        if mapping.id_column:
            required.append(mapping.id_column)
        if not set(required) <= set(columns):
            raise ImportErrorDetail("Colunas mapeadas não encontradas.")
        digest = hashlib.sha256(content).hexdigest()
        entries: list[ParsedEntry] = []
        identifiers: set[str] = set()
        for number, row in enumerate(reader, start=2):
            if len(entries) >= MAX_ROWS or None in row or any(row.get(c) is None for c in required):
                raise ImportErrorDetail("Linha incompleta ou limite de 5.000 lançamentos excedido.")
            identity = f"csv:{digest}:{number}"
            if mapping.id_column:
                external = row[mapping.id_column].strip()
                if not external or external in identifiers:
                    raise ImportErrorDetail("Identificador de lançamento vazio ou duplicado.")
                identifiers.add(external)
                identity = "csv-id:" + hashlib.sha256(external.encode()).hexdigest()
            amount = parse_money(row[mapping.amount_column], mapping.decimal_separator)
            entries.append(
                ParsedEntry(
                    booked_on=parse_date(row[mapping.date_column]),
                    amount_cents=-amount if mapping.debit_positive else amount,
                    description=row[mapping.description_column].strip(),
                    source_identity=identity,
                )
            )
        if not entries:
            raise ImportErrorDetail("Arquivo sem lançamentos.")
        return entries
    except (csv.Error, UnicodeError, ValueError) as error:
        if isinstance(error, ImportErrorDetail):
            raise
        raise ImportErrorDetail("CSV inválido; confira estrutura e campos.") from None
