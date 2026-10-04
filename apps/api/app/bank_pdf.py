"""Layouts textuais observados; sem inferência de valores por LLM."""

import hashlib
import re
from datetime import date

from app.import_parsers import MAX_ROWS, ImportErrorDetail, ParsedEntry, parse_money

MONTHS = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]
SHORT_MONTHS = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
MONEY = r"\d+(?:\.\d{3})*,\d{2}"


def bank_layout(text: str) -> str | None:
    if "PicPay" in text and "Extrato de conta" in text:
        return "picpay"
    if "Extrato de Conta Corrente" in text and "Data Lançamento Valor (R$)" in text:
        return "banestes"
    return None


def parse_bank_statement(text: str, content: bytes) -> list[ParsedEntry]:
    try:
        layout = bank_layout(text)
        rows = picpay_rows(text) if layout == "picpay" else banestes_rows(text)
        if layout is None or not rows or len(rows) > MAX_ROWS:
            raise ValueError
        digest = hashlib.sha256(content).hexdigest()
        return [
            ParsedEntry(
                booked_on=day,
                amount_cents=amount,
                description=description,
                source_identity=f"pdf:{digest}:{index}",
            )
            for index, (day, amount, description) in enumerate(rows)
        ]
    except (ValueError, IndexError):
        raise ImportErrorDetail(
            "Extrato PDF sem movimentações ou com layout divergente; não foi importado."
        ) from None


def picpay_rows(text: str) -> list[tuple[date, int, str]]:
    rows: list[tuple[date, int, str]] = []
    current: date | None = None
    for line in text.splitlines():
        header = re.match(r"(\d{1,2}) de (\w+) (\d{4}) Saldo", line.strip())
        if header:
            current = date(int(header[3]), MONTHS.index(header[2].lower()) + 1, int(header[1]))
        if not re.match(r"^\d{2}:\d{2}\s", line.strip()):
            continue
        row = re.match(rf"^\d{{2}}:\d{{2}} (.+?) ([+−-])R\$ ({MONEY})(.*)$", line.strip())
        if row is None or current is None:
            raise ValueError
        amount = parse_money(row[3], ",") * (1 if row[2] == "+" else -1)
        # Nome da operação basta; contraparte multilinha não é adivinhada.
        rows.append((current, amount, row[1].strip()))
    return rows


def banestes_rows(text: str) -> list[tuple[date, int, str]]:
    body = text.split("Data Lançamento Valor (R$)", 1)[1]
    body = re.sub(r"(?m)^\s*([A-Z]{3}/\d{2})\s+([^\n]+)", r"\1\n\2", body)
    lines = body.splitlines()
    rows: list[tuple[date, int, str]] = []
    blocks: list[tuple[int, list[str]]] = []
    for line in lines:
        line = line.strip()
        if line.lower() in {"resumo", "saldos"}:
            break
        if re.fullmatch(r"\d{2}", line):
            blocks.append((int(line), []))
        elif blocks and line:
            blocks[-1][1].append(line)
    for day, block in blocks:
        markers = [re.fullmatch(r"([A-Z]{3})/(\d{2})", line) for line in block]
        dates = [m for m in markers if m]
        if len(dates) != 1:
            raise ValueError
        current = date(2000 + int(dates[0][2]), SHORT_MONTHS.index(dates[0][1]) + 1, day)
        pending = ""
        for line in block:
            if re.fullmatch(r"[A-Z]{3}/\d{2}", line):
                continue
            if line.startswith("Saldo "):
                if pending:
                    raise ValueError
                continue
            if pending and re.match(
                r"^(Pix|Rendimento|Tarifa|Seguro|Débito|Compra|Pagamento)\b", line
            ):
                raise ValueError
            pending = (pending + " " + line).strip()
            row = re.fullmatch(rf"(.+?)\s+(-\s*)?({MONEY})", pending)
            if row:
                if row[3] != "0,00":
                    amount = parse_money(row[3], ",") * (-1 if row[2] else 1)
                    rows.append((current, amount, row[1].strip()))
                pending = ""
        if pending:
            raise ValueError
    return rows
