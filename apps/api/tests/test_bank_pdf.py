import pytest

from app.bank_pdf import parse_bank_statement
from app.import_parsers import ImportErrorDetail

PICPAY = """Extrato de conta
PicPay
2 de outubro 2026 Saldo no final do dia: R$ 900,00
10:30 Pix enviado −R$ 100,00Pessoa sintetica
1 de outubro 2026 Saldo no final do dia: R$ 1.000,00
09:00 Pix recebido +R$ 1.000,00Pessoa sintetica
"""
BANESTES = """Extrato de Conta Corrente
Data Lançamento Valor (R$)
Saldo Anterior 100,00
02
Pix Recebido contraparte sintetica 50,00
OUT/26 Saldo Conta 150,00
03
Rendimento de aplicacao 0,50
OUT/26
Pix Enviado contraparte
sintetica - 10,00
Tarifa sintetica - 0,00
Saldo Conta 140,50
Resumo
Saldo Total 140,50
"""


def test_bank_pdf_preserves_signed_money_and_ignores_balances():
    picpay = parse_bank_statement(PICPAY, b"synthetic-picpay")
    assert [r.amount_cents for r in picpay] == [-10000, 100000]
    assert [r.booked_on.isoformat() for r in picpay] == ["2026-10-02", "2026-10-01"]
    banestes = parse_bank_statement(BANESTES, b"synthetic-banestes")
    assert [r.amount_cents for r in banestes] == [5000, 50, -1000]
    assert banestes[-1].booked_on.isoformat() == "2026-10-03"
    assert len({r.source_identity for r in banestes}) == 3


@pytest.mark.parametrize(
    "text",
    [
        PICPAY.replace("−R$ 100,00", "R$ 100,00"),
        PICPAY.replace("2 de outubro 2026 Saldo", "cabecalho desconhecido"),
        BANESTES.replace("OUT/26", "XYZ/26"),
        BANESTES.replace("sintetica - 10,00", "sintetica sem valor"),
        "Extrato de Conta Corrente\nData Lançamento Valor (R$)\nSaldo Anterior 100,00",
    ],
)
def test_unknown_or_partial_bank_pdf_is_rejected(text):
    with pytest.raises(ImportErrorDetail):
        parse_bank_statement(text, b"synthetic")
