import pytest
from datetime import date,datetime
from app.models import CurrencyResult
from app.fields import (
    extract_invoice_number,
    extract_invoice_date,
    extract_currency,
)





@pytest.mark.parametrize(
    "text, expected",
    [
        ("Invoice No: FAC-2026-001", "FAC-2026-001"),
        ("Invoice Number: 2026-9981", "2026-9981"),
        ("Facture N° 2026/145", "2026/145"),
        ("N° Facture: 145/2026", "145/2026"),
        ("invoice no FAC2026001", "FAC2026001"),
        ("Some random line", None),
    ],
)
def test_extract_invoice_number(text, expected):
    assert extract_invoice_number(text) == expected


def test_extract_invoice_number_from_ref_label():
    text = (
        "Facture\n"
        "Réf. : FA-2026-001\n"
        "Date : 12/09/2026\n"
    )

    assert extract_invoice_number(text) == "FA-2026-001"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Invoice Date: 2026-09-07", date(2026, 9, 7)),
        ("Date: 07/09/2026", date(2026, 9, 7)),
        ("Date Facture: 07-09-2026", date(2026, 9, 7)),
        ("Facture du 07/09/2026", date(2026, 9, 7)),
        ("Date: 31/02/2026", None),
        ("No date here", None),
    ],
)
def test_extract_invoice_date(text, expected):
    assert extract_invoice_date(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Total: 100 MAD", CurrencyResult.found("MAD")),
        ("Total: 100 DH", CurrencyResult.found("MAD")),
        ("Total: 100 DHS", CurrencyResult.found("MAD")),
        ("Total: €100", CurrencyResult.found("EUR")),
        ("Total: $100", CurrencyResult.found("USD")),
        ("Currency: CAD", CurrencyResult.found("CAD")),
        ("Currency: mad", CurrencyResult.found("MAD")),
        ("MAD MAD MAD", CurrencyResult.found("MAD")),
        ("50 USD ($50)", CurrencyResult.found("USD")),
        (
            "50 USD or 45 EUR",
            CurrencyResult.conflicting({"USD", "EUR"}),
        ),
        (
            "$50 and €45",
            CurrencyResult.conflicting({"USD", "EUR"}),
        ),
        (
            "100 MAD and €20",
            CurrencyResult.conflicting({"MAD", "EUR"}),
        ),
        ("No currency here", CurrencyResult.missing()),
    ],
)
def test_extract_currency(text, expected):
    assert extract_currency(text) == expected
