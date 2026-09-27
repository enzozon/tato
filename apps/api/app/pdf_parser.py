import hashlib
import re

from app.import_parsers import MAX_ROWS, ImportErrorDetail, ParsedEntry, parse_date, parse_money


def parse_invoice(text: str, content: bytes) -> list[ParsedEntry]:
    """Layout textual explícito: data completa, descrição e valor em reais."""
    digest = hashlib.sha256(content).hexdigest()
    entries: list[ParsedEntry] = []
    for number, line in enumerate(text.splitlines()):
        line = line.strip()
        if not re.match(r"^(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\s", line):
            continue
        match = re.fullmatch(r"(\S+)\s+(.+?)\s+([+-]?[\d.]+,\d{2})", line)
        if match is None or len(entries) >= MAX_ROWS:
            raise ImportErrorDetail("Linha de fatura ambígua ou limite de lançamentos excedido.")
        booked, description, amount = match.groups()
        if not description.strip() or len(description) > 5000:
            raise ImportErrorDetail("Descrição de fatura inválida.")
        entries.append(
            ParsedEntry(
                booked_on=parse_date(booked),
                amount_cents=-parse_money(amount, ","),
                description=description,
                source_identity=f"pdf:{digest}:{number}",
            )
        )
    if not entries:
        raise ImportErrorDetail(
            "Layout PDF não reconhecido; exporte CSV/OFX ou use datas completas."
        )
    return entries
