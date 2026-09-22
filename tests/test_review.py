from datetime import date
from decimal import Decimal

import pytest

from app.models import (
    CurrencyResult,
    ExtractedInvoiceData,
    ExtractionResult,
    ReviewIssue,
    ReviewResult,
    TaxIdResult,
)
from app.pipeline import extract_invoice
from app.review import (
    InvoiceNotReadyError,
    finalize_invoice,
    is_totals_consistent,
    review_invoice,
)


@pytest.mark.parametrize(
    "subtotal, tax_amount, total_amount, expected",
    [
        (
            Decimal("1000"),
            Decimal("200"),
            Decimal("1200"),
            True,
        ),
        (
            Decimal("1000"),
            Decimal("200"),
            Decimal("1300"),
            False,
        ),
        (None, Decimal("200"), Decimal("1200"), None),
        (Decimal("1000"), None, Decimal("1200"), None),
        (Decimal("1000"), Decimal("200"), None, None),
    ],
)
def test_is_totals_consistent(
    subtotal,
    tax_amount,
    total_amount,
    expected,
):
    assert (
        is_totals_consistent(
            subtotal,
            tax_amount,
            total_amount,
        )
        == expected
    )



WARNING = ReviewIssue(
    field="total_amount",
    code="inconsistent_totals",
    message="Subtotal + tax amount does not equal total amount.",
    severity="warning",
)

ERROR = ReviewIssue(
    field="invoice_number",
    code="missing_required_field",
    message="Invoice number is missing.",
    severity="error",
)

@pytest.mark.parametrize(
    "issues, expected",
    [
        ([], "ready"),
        ([WARNING], "needs_review"),
        ([ERROR], "blocked"),
        ([WARNING, ERROR], "blocked"),
        ([ERROR, WARNING], "blocked"),
    ],
)
def test_review_result_status(issues, expected):
    result = ReviewResult(
        data=ExtractedInvoiceData(),
        issues=issues,
    )

    assert result.status == expected

READY_TEXT = (
    "Facture N° 2026/145\n"
    "Date de facture: 05/09/2026\n"
    "Subtotal: 1000 MAD\n"
    "Supplier: ACME SARL\n"
    "TVA: 200 MAD\n"
    "Total TTC: 1200 MAD\n"
    "Currency: MAD"
)
 
 
def test_ready_invoice_returns_invoice_data_with_correct_fields():
    extraction = extract_invoice(READY_TEXT)
    review = review_invoice(extraction)
    assert review.status == "ready"
 
    invoice = finalize_invoice(extraction, review)
 
    assert invoice.invoice_number == "2026/145"
    assert invoice.invoice_date == date(2026, 9, 5)
    assert invoice.total_amount == Decimal("1200")
    assert invoice.currency == "MAD"


def test_blocked_invoice_raises_with_status_and_issues_preserved():
    # Missing invoice_number, invoice_date, and currency entirely.
    extraction = extract_invoice("Total TTC: 1200")
    review = review_invoice(extraction)
    assert review.status == "blocked"
 
    with pytest.raises(InvoiceNotReadyError) as exc_info:
        finalize_invoice(extraction, review)
 
    assert exc_info.value.status == "blocked"
    assert exc_info.value.issues == review.issues
    assert len(exc_info.value.issues) > 0
 
 
def test_needs_review_invoice_raises_with_status_and_issues_preserved():
    # Otherwise-clean invoice, but with an invalid (wrong-length) customer ICE.
    extraction = extract_invoice(READY_TEXT + "\nClient ICE: 12345")
    review = review_invoice(extraction)
    assert review.status == "needs_review"
 
    with pytest.raises(InvoiceNotReadyError) as exc_info:
        finalize_invoice(extraction, review)
 
    assert exc_info.value.status == "needs_review"
    assert exc_info.value.issues == review.issues
    assert len(exc_info.value.issues) > 0


def _valid_data(**overrides) -> ExtractedInvoiceData:
    values = {
        "invoice_number": "FAC-2026-001",
        "invoice_date": date(2026, 9, 7),
        "supplier_name" :"ACME SARL",
        "subtotal": Decimal("1000"),
        "tax_amount": Decimal("200"),
        "total_amount": Decimal("1200"),
        "currency": "MAD",
    }

    values.update(overrides)

    return ExtractedInvoiceData(**values)


def _extraction_result(
    *,
    data: ExtractedInvoiceData | None = None,
    currency_result: CurrencyResult | None = None,
    customer_ice_result: TaxIdResult | None = None,
    supplier_tax_id_result: TaxIdResult | None = None,
) -> ExtractionResult:
    return ExtractionResult(
        data=data or _valid_data(),
        currency_result=currency_result or CurrencyResult.found("MAD"),
        customer_ice_result=customer_ice_result or TaxIdResult.missing(),
        supplier_tax_id_result=supplier_tax_id_result or TaxIdResult.missing(),
    )


def test_valid_invoice_is_ready():
    result = review_invoice(
        _extraction_result()
        )

    assert result.status == "ready"
    assert result.issues == []


def test_missing_required_field_blocks_invoice():
    result = review_invoice(
        _extraction_result(
            data=_valid_data(invoice_number=None)
        )
    )

    assert result.status == "blocked"

    assert any(
        issue.field == "invoice_number"
        and issue.code == "missing_required_field"
        for issue in result.issues
    )


def test_missing_currency_blocks_invoice():
    result = review_invoice(
            _extraction_result(
            data=_valid_data(currency=None),
            currency_result=CurrencyResult.missing(),
        )
    )

    assert result.status == "blocked"

    assert any(
        issue.field == "currency"
        and issue.code == "missing_required_field"
        for issue in result.issues
    )


def test_conflicting_currency_blocks_invoice():
    result = review_invoice(
        _extraction_result(
            data=_valid_data(currency=None),
            currency_result=CurrencyResult.conflicting(
                {"MAD", "EUR"}
            ),
        )
    )

    assert result.status == "blocked"

    assert any(
        issue.code == "conflicting_currency"
        for issue in result.issues
    )


def test_invalid_customer_ice_requires_review():
    result = review_invoice(
       _extraction_result(
            data=_valid_data(customer_ICE="12345"),
            customer_ice_result=TaxIdResult.found(
                "ICE",
                "12345",
            ),
        )
    )

    assert result.status == "needs_review"

    assert any(
        issue.code == "invalid_ice"
        for issue in result.issues
    )


def test_inconsistent_totals_require_review():
    result = review_invoice(
        _extraction_result(
            data=_valid_data(
                total_amount=Decimal("1300")
            )
        )
    )

    assert result.status == "needs_review"

    assert any(
        issue.code == "inconsistent_totals"
        for issue in result.issues
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"subtotal": None},
        {"tax_amount": None},
    ],
)
def test_incomplete_totals_do_not_create_false_warning(overrides):
    result = review_invoice(
      _extraction_result(
            data=_valid_data(**overrides)
        )
    )

    assert not any(
        issue.code == "inconsistent_totals"
        for issue in result.issues
    )


def test_error_takes_priority_over_warning():
    result = review_invoice(
         _extraction_result(
            data=_valid_data(
                invoice_number=None,
                total_amount=Decimal("1300"),
            )
        )
    )

    assert any(
        issue.severity == "error"
        for issue in result.issues
    )

    assert any(
        issue.severity == "warning"
        for issue in result.issues
    )

    assert result.status == "blocked"


def test_conflicting_customer_ice_requires_review():
    result = review_invoice(
        _extraction_result(
            data=_valid_data(customer_ICE=None),
            customer_ice_result=TaxIdResult.conflicting(
                "ICE",
                {
                    "001234567000001",
                    "009876543000002",
                },
            ),
        )
    )

    assert result.status == "needs_review"
    assert any(
        issue.code == "conflicting_ice"
        for issue in result.issues
    )

def test_conflicting_supplier_tax_id_requires_review():
    result = review_invoice(
        _extraction_result(
            supplier_tax_id_result=TaxIdResult.conflicting(
                "ICE",
                {
                    "001234567000001",
                    "009876543000002",
                },
            ),
        )
    )

    assert result.status == "needs_review"
    assert any(
        issue.code == "conflicting_tax_id"
        for issue in result.issues
    )


def test_missing_supplier_name_blocks_invoice():
    text = """
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Total TTC: 1200 MAD
"""

    extraction = extract_invoice(text)
    review = review_invoice(extraction)

    assert review.status == "blocked"
    assert any(
        issue.field == "supplier_name"
        and issue.code == "missing_required_field"
        for issue in review.issues
    )
