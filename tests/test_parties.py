import pytest

from app.parties import (
    extract_customer_name,
    extract_supplier_name,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Supplier: ACME SARL", "ACME SARL"),
        ("Fournisseur : Atlas Tech", "Atlas Tech"),
        ("Vendor: Example Inc.", "Example Inc."),
        ("Supplier - ACME SARL", "ACME SARL"),
        ("Supplier:", None),
        ("Invoice No: FAC-001", None),
        ("Supplier ICE: 001234567000089", None),
        ("Supplier: ICE: 001234567000089", None),
    ],
)
def test_extract_supplier_name(text, expected):
    assert extract_supplier_name(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Customer: ACME SARL", "ACME SARL"),
        ("Client : Atlas Tech", "Atlas Tech"),
        ("Bill To: Example Inc.", "Example Inc."),
        ("Facturé à: Société X", "Société X"),
        ("Facture à: Société X", "Société X"),
        ("Customer - ACME SARL", "ACME SARL"),
        ("Customer:", None),
        ("Invoice No: FAC-001", None),
        ("Client ICE: 001234567000089", None),
        ("Customer: ICE: 001234567000089", None),
    ],
)
def test_extract_customer_name(text, expected):
    assert extract_customer_name(text) == expected


def test_extract_supplier_name_from_emetteur_section():
    text = (
        "EMETTEUR\n"
        "Atelier Zellige SARL\n"
        "12 Rue des Artisans, Casablanca\n"
        "ICE : 001234567000089\n"
        "IF : 45219800\n"
        "CLIENT\n"
        "Societe Nord Trading SARL\n"
    )

    assert extract_supplier_name(text) == "Atelier Zellige SARL"


def test_extract_customer_name_from_client_section():
    text = (
        "EMETTEUR\n"
        "Atelier Zellige SARL\n"
        "12 Rue des Artisans, Casablanca\n"
        "CLIENT\n"
        "Societe Nord Trading SARL\n"
        "8 Avenue Hassan II, Rabat\n"
    )

    assert extract_customer_name(text) == "Societe Nord Trading SARL"


def test_customer_company_name_starting_with_client_is_not_truncated():
    text = "Émetteur : Adressé à :\nVOTRE SOCIÉTÉ SARL\nCLIENT EXEMPLE SARL\n"

    result = extract_customer_name(text)

    assert result != "EXEMPLE SARL"


def test_supplier_name_does_not_capture_adresse_a_heading():
    text = (
        "Émetteur :\n"
        "Adressé à :\n"
        "VOTRE SOCIÉTÉ SARL\n"
        "12 rue de l'Exemple\n"
        "Casablanca\n"
        "CLIENT EXEMPLE SARL\n"
    )

    result = extract_supplier_name(text)

    assert result != "Adressé à :"
    assert result == "VOTRE SOCIÉTÉ SARL"


def test_extract_customer_name_from_mparsio_two_column_layout():
    text = (
        "Émetteur :\n"
        "Adressé à :\n"
        "VOTRE SOCIÉTÉ SARL\n"
        "12 rue de l'Exemple\n"
        "Quartier des Affaires\n"
        "Casablanca\n"
        "CLIENT EXEMPLE SARL\n"
        "I.C.E : 111111111111111\n"
        "Rabat\n"
    )

    assert extract_customer_name(text) == "CLIENT EXEMPLE SARL"
