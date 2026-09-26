from decimal import Decimal

import pytest

from app.amounts import (
    extract_subtotal_amount,
    extract_tax_amount,
    extract_total_amount,
    normalize_amount,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1 250,50", Decimal("1250.50")),
        ("1250.50", Decimal("1250.50")),
        ("12,500.00", Decimal("12500.00")),
        ("12.500,00", Decimal("12500.00")),
        ("1,250", Decimal("1250")),
        ("1.250", Decimal("1250")),
        ("1250", Decimal("1250")),
        ("abc", None),
    ],
)
def test_normalize_amount(raw, expected):
    assert normalize_amount(raw) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Total: 1250.50 MAD", Decimal("1250.50")),
        ("Total TTC: 1 250,50 MAD", Decimal("1250.50")),
        ("Montant TTC: 12,500.00 MAD", Decimal("12500.00")),
        ("Total: 1250 MAD", Decimal("1250")),
        ("No total here", None),
        ("Sous-total: 900 MAD", None),
    ],
)
def test_extract_total_amount(text, expected):
    assert extract_total_amount(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("TVA: 200 MAD", Decimal("200")),
        ("VAT: 20.00 USD", Decimal("20.00")),
        ("Tax: 15 EUR", Decimal("15")),
        ("Tax Amount: 200 MAD", Decimal("200")),
        ("Tax Amount - 200 MAD", Decimal("200")),
        ("VAT 20.00 USD", Decimal("20.00")),
        ("Total TTC: 1200 MAD", None),
        ("No tax here", None),
    ],
)
def test_extract_tax_amount(text, expected):
    assert extract_tax_amount(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Sous-total: 1000 MAD", Decimal("1000")),
        ("Sous total: 1 000,50 MAD", Decimal("1000.50")),
        ("Subtotal: 1250.00 USD", Decimal("1250.00")),
        ("No subtotal here", None),
    ],
)
def test_extract_subtotal_amount(text, expected):
    assert extract_subtotal_amount(text) == expected


def test_extract_total_amount_with_space_thousands_separator():
    text = "Total TTC : 5 820,00 DH"

    assert extract_total_amount(text) == Decimal("5820.00")


def test_extract_subtotal_with_space_thousands_separator():
    text = "Total HT : 4 850,00 DH"

    assert extract_subtotal_amount(text) == Decimal("4850.00")


def test_extract_tax_amount_with_percentage_between_label_and_amount():
    text = "TVA (20%) : 970,00 DH"

    assert extract_tax_amount(text) == Decimal("970.00")


def test_extract_tax_amount_total_tva_with_percentage():
    text = "Total TVA 20% 1 840,00"

    assert extract_tax_amount(text) == Decimal("1840.00")


def test_extract_tax_amount_when_totals_share_same_line():
    text = "Total HT : 4 850,00 DH   TVA (20%) : 970,00 DH   Total TTC : 5 820,00 DH"

    assert extract_tax_amount(text) == Decimal("970.00")


def test_extract_total_amount_when_totals_share_same_line():
    text = "Total HT : 4 850,00 DH   TVA (20%) : 970,00 DH   Total TTC : 5 820,00 DH"

    assert extract_total_amount(text) == Decimal("5820.00")


def test_extract_subtotal_amount_when_value_is_on_next_line():
    text = "Total HT\n9 200,00\n"

    assert extract_subtotal_amount(text) == Decimal("9200.00")


def test_extract_tax_amount_when_value_is_on_next_line_after_rate():
    text = "Total TVA 20%\n1 840,00\n"

    assert extract_tax_amount(text) == Decimal("1840.00")


def test_extract_total_amount_when_value_is_on_next_line():
    text = "Total TTC\n11 040,00\n"

    assert extract_total_amount(text) == Decimal("11040.00")


def test_labelled_grand_total_wins_over_earlier_bare_total():
    text = "Total : 1 000,00 DH\nTVA 20% : 200,00 DH\nTotal TTC : 1 200,00 DH\n"

    assert extract_total_amount(text) == Decimal("1200.00")


def test_bare_total_is_still_used_without_a_labelled_grand_total():
    text = "Subtotal: 1,000.00\nTax: 100.00\nTotal: 1,100.00\n"

    assert extract_total_amount(text) == Decimal("1100.00")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("TVA : 20 %\nTotal TVA : 200,00 DH", Decimal("200.00")),
        ("TVA 20 %\nTotal TVA : 200,00 DH", Decimal("200.00")),
        ("TVA : 20 %", None),
        ("VAT: 20%", None),
        ("TVA : 7,5 %", None),
    ],
)
def test_tax_rate_is_not_read_as_tax_amount(text, expected):
    assert extract_tax_amount(text) == expected
