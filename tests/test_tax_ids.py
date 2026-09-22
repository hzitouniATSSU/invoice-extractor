import pytest

from app.pipeline import extract_invoice
from app.tax_ids import (
    extract_tax_id_by_party,
    is_valid_ice,
    select_customer_ice_result,
    select_supplier_tax_id_result,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("001234567000089", True),
        ("001 234 567 000 089", True),
        ("00123456700008", False),
        ("0012345670000899", False),
        ("00123456700008A", False),
        ("001-234-567-000-089", False),
        ("", False),
    ],
)
def test_is_valid_ice(value, expected):
    assert is_valid_ice(value) == expected

@pytest.mark.parametrize(
    "entries, expected_status, expected_value",
    [
        ([("ICE", "001234567000089")], "found", "001234567000089"),
        (
            [
                ("ICE", "001234567000089"),
                ("ICE", "001234567000089"),
            ],
            "found",
            "001234567000089",
        ),
        (
            [
                ("ICE", "001234567000089"),
                ("ICE", "999999999999999"),
            ],
            "conflicting",
            None,
        ),
        ([], "missing", None),
    ],
)
def test_select_customer_ice(entries, expected_status, expected_value):
    result = select_customer_ice_result(entries)

    assert result.status == expected_status
    assert result.value == expected_value


@pytest.mark.parametrize(
    "entries, expected_status, expected_value",
    [
        (
            [
                ("ICE", "001234567000000"),
                ("IF", "87654321"),
            ],
            "found",
            "001234567000000",
        ),
        (
            [
                ("ICE", "001234567000000"),
                ("ICE", "001234567000000"),
            ],
            "found",
            "001234567000000",
        ),
        (
            [
                ("ICE", "001234567000000"),
                ("ICE", "999999999999999"),
            ],
            "conflicting",
            None,
        ),
        ([("IF", "87654321")], "found", "87654321"),
        (
            [("IDENTIFIANT FISCAL", "33333333")],
            "found",
            "33333333",
        ),
        ([], "missing", None),
    ],
)
def test_select_supplier_tax_id(entries, expected_status, expected_value):
    result = select_supplier_tax_id_result(entries)

    assert result.status == expected_status
    assert result.value == expected_value


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "Client IF: 12345678",
            {"customer": [("IF", "12345678")]},
        ),
        (
            "Client Tax ID: ABC-123456",
            {"customer": [("TAX ID", "ABC-123456")]},
        ),
        (
            "ICE Client: 001234567000089",
            {"customer": [("ICE", "001234567000089")]},
        ),
        (
            "Supplier Identifiant Fiscal: 12345678",
            {"supplier": [("IDENTIFIANT FISCAL", "12345678")]},
        ),
        (
            "Fournisseur ICE: 001234567000000\n"
            "Client ICE: 009876543000012",
            {
                "supplier": [("ICE", "001234567000000")],
                "customer": [("ICE", "009876543000012")],
            },
        ),
    ],
)
def test_extract_tax_id_by_party(text, expected):
    assert extract_tax_id_by_party(text) == expected


def test_extract_customer_ice_from_mparsio_customer_block():
    text = (
        "CLIENT EXEMPLE SARL\n"
        "I.C.E : 111111111111111\n"
        "Rabat\n"
    )

    result = extract_invoice(text)

    assert result.data.customer_ICE == "111111111111111"


def test_extract_supplier_tax_id_from_company_footer():
    text = (
        "Siège social : VOTRE SOCIÉTÉ SARL - 12 rue de l'Exemple\n"
        "contact@votresociete.ma\n"
        "R.C : 000000 - I.F : 00000000 - "
        "I.C.E : 000000000000000 - T.P : 00000000\n"
    )

    result = extract_invoice(text)

    assert result.data.supplier_tax_id == "000000000000000"

def test_extract_supplier_ice_from_emetteur_section():
    text = (
        "EMETTEUR\n"
        "Atelier Zellige SARL\n"
        "12 Rue des Artisans, Casablanca\n"
        "ICE : 001234567000089\n"
        "IF : 45219800\n"
        "CLIENT\n"
        "Societe Nord Trading SARL\n"
    )

    result = extract_invoice(text)

    assert result.data.supplier_tax_id == "001234567000089"