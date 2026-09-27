import hashlib
import re
from datetime import datetime
from html import unescape

from app.import_parsers import MAX_ROWS, ImportErrorDetail, ParsedEntry, decode_file, parse_money


def field(block: str, name: str, required: bool = True) -> str:
    matches = re.findall(rf"<{name}>\s*([^<]*)", block, flags=re.IGNORECASE)
    if len(matches) > 1 or (required and (not matches or not matches[0].strip())):
        raise ImportErrorDetail("Campo OFX obrigatório ausente ou duplicado.")
    return unescape(matches[0].strip()) if matches else ""


def parse_ofx(content: bytes) -> list[ParsedEntry]:
    text = decode_file(content)
    if re.search(r"<!DOCTYPE|<!ENTITY|<CORRECTFITID|<CORRECTACTION", text, re.IGNORECASE):
        raise ImportErrorDetail("OFX com entidades ou correções não suportadas.")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    if not re.search(r"<OFX>", text, re.IGNORECASE):
        raise ImportErrorDetail("Estrutura OFX não encontrada.")
    statements = re.findall(r"<(?:STMTRS|CCSTMTRS)>", text, re.IGNORECASE)
    if len(statements) != 1 or field(text, "CURDEF") != "BRL":
        raise ImportErrorDetail("Importe somente um extrato em BRL por arquivo.")
    for status in re.findall(r"<STATUS>(.*?)</STATUS>", text, re.DOTALL | re.IGNORECASE):
        if field(status, "CODE") != "0":
            raise ImportErrorDetail("O banco retornou erro no arquivo OFX.")
    blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, re.DOTALL | re.IGNORECASE)
    if (
        not blocks
        or len(blocks) > MAX_ROWS
        or len(blocks) != len(re.findall(r"<STMTTRN>", text, re.IGNORECASE))
    ):
        raise ImportErrorDetail("OFX vazio, incompleto ou com mais de 5.000 lançamentos.")
    entries: list[ParsedEntry] = []
    identities: set[str] = set()
    try:
        for block in blocks:
            identity = field(block, "FITID")
            if identity in identities or len(identity) > 256:
                raise ImportErrorDetail("FITID duplicado ou excessivamente longo.")
            identities.add(identity)
            raw_date = field(block, "DTPOSTED")
            if not re.fullmatch(
                r"\d{8}(?:\d{6}(?:\.\d{1,3})?)?(?:\[[+-]?\d{1,2}(?:\.\d+)?:[A-Za-z]{1,8}\])?",
                raw_date,
            ):
                raise ImportErrorDetail("Data OFX inválida.")
            entries.append(
                ParsedEntry(
                    booked_on=datetime.strptime(raw_date[:8], "%Y%m%d").date(),
                    amount_cents=parse_money(field(block, "TRNAMT"), "."),
                    description=field(block, "MEMO", False) or field(block, "NAME"),
                    source_identity="ofx-id:" + hashlib.sha256(identity.encode()).hexdigest(),
                    kind="transfer" if field(block, "TRNTYPE", False) == "XFER" else None,
                )
            )
    except ValueError as error:
        if isinstance(error, ImportErrorDetail):
            raise
        raise ImportErrorDetail("OFX inválido; confira datas e campos.") from None
    return entries
