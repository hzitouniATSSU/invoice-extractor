from datetime import date
from decimal import Decimal

from app.models import CurrencyResult
from app.pipeline import extract_invoice, extract_invoice_data
from app.review import review_invoice


def test_extract_invoice_data_populates_expected_fields():
    text = """
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Supplier: ACME SARL
Fournisseur ICE: 001234567000000
Customer: Société X
Client ICE: 009876543000012
Subtotal: 1000 MAD
TVA: 200 MAD
Total TTC: 1200 MAD
"""

    result = extract_invoice_data(text)

    assert result.invoice_number == "FAC-2026-001"
    assert result.invoice_date == date(2026, 9, 7)
    assert result.supplier_name == "ACME SARL"
    assert result.supplier_tax_id == "001234567000000"
    assert result.customer_name == "Société X"
    assert result.customer_ICE == "009876543000012"
    assert result.subtotal == Decimal("1000")
    assert result.tax_amount == Decimal("200")
    assert result.total_amount == Decimal("1200")
    assert result.currency == "MAD"


def test_extract_invoice_preserves_currency_metadata():
    text = """
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Total TTC: 1200 MAD
"""

    result = extract_invoice(text)

    assert result.data.currency == "MAD"
    assert result.currency_result == CurrencyResult.found("MAD")


def test_extract_invoice_preserves_currency_conflict():
    text = """
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Total TTC: 1200 MAD
Other charge: €20
"""

    result = extract_invoice(text)

    assert result.data.currency is None

    assert result.currency_result == CurrencyResult.conflicting(
        {"MAD", "EUR"}
    )


def test_pipeline_clean_invoice_is_ready():
    text = """
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Supplier: ACME SARL
Customer: Société X
Client ICE: 009876543000012
Subtotal: 1000 MAD
TVA: 200 MAD
Total TTC: 1200 MAD
"""

    extraction = extract_invoice(text)
    review = review_invoice(extraction)

    assert review.status == "ready"
    assert review.issues == []


def test_pipeline_conflicting_currency_is_blocked():
    text = """
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Total TTC: 1200 MAD
Service fee: €20
"""

    extraction = extract_invoice(text)
    review = review_invoice(extraction)

    assert review.status == "blocked"
    assert any(
        issue.code == "conflicting_currency"
        for issue in review.issues
    )


def test_pipeline_conflicting_customer_ice_needs_review():
    text = """
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Supplier: ACME SARL
Client ICE: 001234567000001
Client ICE: 009876543000002
Total TTC: 1200 MAD
"""

    extraction = extract_invoice(text)
    review = review_invoice(extraction)

    assert review.status == "needs_review"
    assert any(
        issue.code == "conflicting_ice"
        for issue in review.issues
    )