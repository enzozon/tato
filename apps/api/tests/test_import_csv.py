import pytest

from app.import_parsers import CsvMapping, ImportErrorDetail, parse_csv, parse_money


@pytest.mark.parametrize(
    ("raw", "separator", "expected"),
    [
        ("-1.234,56", ",", -123456),
        ("1,234.56", ".", 123456),
        ("90071992547409.93", ".", 9007199254740993),
    ],
)
def test_money_is_exact(raw, separator, expected):
    assert parse_money(raw, separator) == expected


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "1e3", "1,234", "0", "--2", "9" * 25])
def test_money_rejects_ambiguous_or_invalid_values(raw):
    with pytest.raises(ImportErrorDetail):
        parse_money(raw, ",")


def test_card_debits_and_refunds_preserve_distinct_purchases():
    data = (
        b"date,title,amount\n2026-09-01,Mercado,42.00\n"
        b"2026-09-01,Mercado,42.00\n2026-09-02,Estorno,-10.00\n"
    )
    rows = parse_csv(data)
    assert [r.amount_cents for r in rows] == [-4200, -4200, 1000]
    assert rows[0].source_identity != rows[1].source_identity
    assert parse_csv(data) == rows


def test_mapping_supports_portuguese_and_cp1252():
    data = "Dia;Texto;Total;Código\n01/09/2026;Compra sintética;-42,10;1\n".encode("cp1252")
    mapping = CsvMapping(
        date_column="Dia", description_column="Texto", amount_column="Total", id_column="Código"
    )
    rows = parse_csv(data, mapping)
    assert rows[0].amount_cents == -4210
    assert rows[0].booked_on.isoformat() == "2026-09-01"


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"a,a\n1,2\n",
        b"date,title,amount\n2026-99-01,private,1\n",
        b"date,title,amount\n2026-09-01,private,1,extra\n",
    ],
)
def test_bad_csv_does_not_echo_financial_content(data):
    with pytest.raises(ImportErrorDetail) as error:
        parse_csv(data)
    assert "private" not in str(error.value)
