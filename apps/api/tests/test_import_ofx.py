import pytest

from app.import_parsers import ImportErrorDetail
from app.ofx_parser import parse_ofx


def statement(
    identifier="synthetic-1", date="20260901120000[-3:BRT]", memo="Mercado &amp; padaria"
):
    return f"<STMTTRN><DTPOSTED>{date}<TRNAMT>-42.10<FITID>{identifier}<MEMO>{memo}</STMTTRN>"


def ofx(rows):
    return (
        f"OFXHEADER:100\n\n<OFX><STMTRS><CURDEF>BRL<BANKTRANLIST>{rows}"
        "</BANKTRANLIST></STMTRS></OFX>"
    ).encode()


def test_sgml_preserves_identity_across_exports():
    first = parse_ofx(ofx(statement()))[0]
    second = parse_ofx(ofx(statement(memo="Descrição alterada")))[0]
    assert first.amount_cents == -4210
    assert first.description == "Mercado & padaria"
    assert first.booked_on.isoformat() == "2026-09-01"
    assert first.source_identity == second.source_identity


def test_xml_closed_leaves_supported():
    data = ofx(
        "<STMTTRN><DTPOSTED>20260901</DTPOSTED><TRNAMT>10.50</TRNAMT>"
        "<FITID>id2</FITID><NAME>Estorno</NAME></STMTTRN>"
    )
    assert parse_ofx(data)[0].amount_cents == 1050


@pytest.mark.parametrize(
    "data",
    [
        b"<!DOCTYPE OFX><OFX>",
        ofx(statement() + statement()),
        ofx(""),
        ofx(statement(date="20269901")),
        ofx(statement()).replace(b"BRL", b"USD"),
        ofx(statement()).replace(b"</STMTTRN>", b""),
        ofx(statement() + "<CORRECTFITID>x"),
    ],
)
def test_invalid_ofx_fails_without_echoing_payload(data):
    with pytest.raises(ImportErrorDetail) as error:
        parse_ofx(data)
    assert "Mercado" not in str(error.value)
