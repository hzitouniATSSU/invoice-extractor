from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import InvoiceData


def _valid_invoice(**overrides) -> InvoiceData:
    base = dict(
        invoice_number="FAC-2026-001",
        invoice_date=date(2026, 9, 7),
        total_amount=Decimal("1200"),
        currency="MAD",
        supplier_name="Atlas Trading Co.",
        customer_name="Jane Doe",
        customer_ICE="001234567000089",
        supplier_tax_id="001234567000000",
        subtotal=Decimal("1000"),
        tax_amount=Decimal("200"),
    )
    base.update(overrides)
    return InvoiceData(**base)


def test_invoice_data_rejects_blank_supplier_name():
    with pytest.raises(ValidationError):
        _valid_invoice(supplier_name="   ")


def test_invoice_data_rejects_blank_invoice_number():
    with pytest.raises(ValidationError):
        _valid_invoice(invoice_number="   ")


def test_invoice_data_normalizes_lowercase_currency():
    invoice = _valid_invoice(currency="mad")

    assert invoice.currency == "MAD"


def test_invoice_data_rejects_unsupported_currency():
    with pytest.raises(ValidationError):
        _valid_invoice(currency="XYZ")


def test_invoice_data_normalizes_whitespace_and_currency():
    invoice = _valid_invoice(
        supplier_name="  ACME SARL  ",
        invoice_number="  FAC-001  ",
        currency=" mad ",
    )

    assert invoice.supplier_name == "ACME SARL"
    assert invoice.invoice_number == "FAC-001"
    assert invoice.currency == "MAD"
