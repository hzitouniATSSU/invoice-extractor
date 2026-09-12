import pytest, csv, openpyxl
from pydantic import ValidationError
from datetime import date,datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
import io

client = TestClient(app)

from app.extractors import (
    extract_invoice_number,
    extract_invoice_date,
    extract_currency,
    extract_supplier_name,
    extract_customer_name,
    is_valid_ice,
    extract_invoice_data,
    extract_invoice,
    
)
from app.amounts import (
    extract_subtotal_amount,
    extract_tax_amount,
    extract_total_amount,
      normalize_amount
)
from app.exporters import export_invoice_to_csv, export_invoice_to_excel
from app.review import review_invoice, finalize_invoice, InvoiceNotReadyError,  is_totals_consistent
from app.tax_ids import extract_tax_id_by_party, select_customer_ice_result, select_supplier_tax_id_result
from app.models import (
    ExtractedInvoiceData,
    ReviewIssue,
    ReviewResult,
    CurrencyResult,
    ExtractionResult,
    TaxIdResult,
    InvoiceData
)
from io import BytesIO
from reportlab.pdfgen import canvas

# ============================================================
# Invoice number
# ============================================================

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


# ============================================================
# Invoice date
# ============================================================

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


# ============================================================
# Amount normalization
# ============================================================

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


# ============================================================
# Total
# ============================================================

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


# ============================================================
# Subtotal
# ============================================================

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


# ============================================================
# Tax amount
# ============================================================

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


# ============================================================
# Currency
# ============================================================

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


# ============================================================
# Supplier / customer names
# ============================================================

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


# ============================================================
# ICE validation
# ============================================================

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


# ============================================================
# Tax ID parsing
# ============================================================

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


# ============================================================
# Tax ID selection
# ============================================================

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

# ============================================================
# Total consistency
# ============================================================

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


# ============================================================
# ExtractedInvoiceData integration
# ============================================================

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


# ============================================================
# ExtractionResult integration
# ============================================================

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


# ============================================================
# ReviewResult status
# ============================================================

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


# ============================================================
# Review logic
# ============================================================

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

# ============================================================
# End to End pipeline tests
# ============================================================


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

#==============================================================
# CSV Export Tests
#==============================================================

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
 
 
def test_export_returns_path_and_creates_file(tmp_path):
    invoice = _valid_invoice()
    output_path = tmp_path / "invoice.csv"
 
    result = export_invoice_to_csv(invoice, output_path)
 
    assert result == output_path
    assert output_path.exists()
 
 
def test_export_csv_values_are_correct(tmp_path):
    invoice = _valid_invoice()
    output_path = tmp_path / "invoice.csv"
    export_invoice_to_csv(invoice, output_path)
 
    with output_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
 
    assert len(rows) == 1
    row = rows[0]
    assert row["invoice_date"] == "2026-09-07"
    assert row["subtotal"] == "1000"
    assert row["tax_amount"] == "200"
    assert row["total_amount"] == "1200"
    assert row["currency"] == "MAD"
    assert row["invoice_number"] == "FAC-2026-001"
    assert row["supplier_name"] == "Atlas Trading Co."
 
 
def test_export_none_fields_become_empty_cells(tmp_path):
    invoice = _valid_invoice(
        supplier_tax_id=None,
        customer_name=None,
        customer_ICE=None,
    )
    output_path = tmp_path / "invoice.csv"
    export_invoice_to_csv(invoice, output_path)
 
    with output_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
 
    row = rows[0]
    assert row["supplier_tax_id"] == ""
    assert row["customer_name"] == ""
    assert row["customer_ICE"] == ""
 
 
def test_export_creates_missing_parent_directories(tmp_path):
    invoice = _valid_invoice()
    output_path = tmp_path / "exports" / "invoices" / "invoice.csv"
 
    assert not output_path.parent.exists()
 
    result = export_invoice_to_csv(invoice, output_path)
 
    assert result == output_path
    assert output_path.exists()


#===============================================================
# Excel Export Test
#=================================================================
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
 
 
def test_export_returns_path_and_creates_file(tmp_path):
    invoice = _valid_invoice()
    output_path = tmp_path / "invoice.xlsx"
 
    result = export_invoice_to_excel(invoice, output_path)
 
    assert result == output_path
    assert output_path.exists()
 
 
def test_workbook_contents_are_correct(tmp_path):
    invoice = _valid_invoice()
    output_path = tmp_path / "invoice.xlsx"
    export_invoice_to_excel(invoice, output_path)
 
    wb = openpyxl.load_workbook(output_path)
    assert "Invoice" in wb.sheetnames
    ws = wb["Invoice"]
 
    headers = [cell.value for cell in ws[1]]
    values = {
        headers[i]: ws.cell(row=2, column=i + 1).value
        for i in range(len(headers))
    }
 
    assert values["invoice_number"] == "FAC-2026-001"
    assert values["supplier_name"] == "Atlas Trading Co."
    assert values["subtotal"] == 1000
    assert values["tax_amount"] == 200
    assert values["total_amount"] == 1200
    assert values["currency"] == "MAD"
 
    # openpyxl may hand back a datetime rather than the original date,
    # depending on serialization -- normalize before comparing.
    invoice_date = values["invoice_date"]
    if isinstance(invoice_date, datetime):
        invoice_date = invoice_date.date()
    assert invoice_date == date(2026, 9, 7)
 
 
def test_optional_fields_remain_blank(tmp_path):
    invoice = _valid_invoice(
        supplier_tax_id=None,
        customer_name=None,
        customer_ICE=None,
    )
    output_path = tmp_path / "invoice.xlsx"
    export_invoice_to_excel(invoice, output_path)
 
    ws = openpyxl.load_workbook(output_path)["Invoice"]
    headers = [cell.value for cell in ws[1]]
    values = {
        headers[i]: ws.cell(row=2, column=i + 1).value
        for i in range(len(headers))
    }
 
    assert values["supplier_tax_id"] is None
    assert values["customer_name"] is None
    assert values["customer_ICE"] is None
 
 
def test_export_creates_missing_parent_directories(tmp_path):
    invoice = _valid_invoice()
    output_path = tmp_path / "exports" / "invoices" / "invoice.xlsx"
 
    assert not output_path.parent.exists()
 
    result = export_invoice_to_excel(invoice, output_path)
 
    assert result == output_path
    assert output_path.exists()


#===============================================================
#
#===============================================================

def _make_pdf(text: str) -> bytes:
    buffer = BytesIO()

    pdf = canvas.Canvas(buffer)
    text_object = pdf.beginText(40, 800)

    for line in text.splitlines():
        text_object.textLine(line)

    pdf.drawText(text_object)
    pdf.save()

    return buffer.getvalue()

def test_extract_endpoint_returns_structured_invoice():
    pdf_bytes = _make_pdf("""
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Supplier: Atlas Trading Co.
Subtotal: 1000 MAD
TVA: 200 MAD
Total TTC: 1200 MAD
""")

    response = client.post(
        "/extract",
        files={
            "file": (
                "invoice.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
    )
    assert response.status_code == 200

    body = response.json()

    assert body["filename"] == "invoice.pdf"
    assert body["status"] == "ready"
    assert body["data"]["invoice_number"] == "FAC-2026-001"
    assert body["data"]["supplier_name"] == "Atlas Trading Co."
    assert body["data"]["total_amount"] == "1200"
    assert body["data"]["currency"] == "MAD"
    assert body["issues"] == []


def test_extract_endpoint_rejects_non_pdf():
    response = client.post(
        "/extract",
        files={
            "file": (
                "invoice.txt",
                b"not a pdf",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid file type. Only PDF files are allowed."
    )

def test_extract_endpoint_rejects_corrupted_pdf():
    response = client.post(
        "/extract",
        files={
            "file": (
                "invoice.pdf",
                b"this is not actually a PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400

def test_extract_endpoint_rejects_pdf_with_no_extractable_text():
    pdf_bytes = _make_pdf("")

    response = client.post(
        "/extract",
        files={
            "file": (
                "empty.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "No extractable text found. "
        "Scanned PDFs are not supported in this version."
    )


def test_export_endpoint_returns_csv():
    pdf_bytes = _make_pdf(READY_TEXT)

    response = client.post(
        "/export?format=csv",
        files={
            "file": (
                "sample-invoice.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "sample-invoice.csv" in response.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(response.text)))

    assert len(rows) == 1

    row = rows[0]
    assert row["invoice_number"] == "2026/145"
    assert row["invoice_date"] == "2026-09-05"
    assert row["supplier_name"] == "ACME SARL"
    assert row["total_amount"] == "1200"
    assert row["currency"] == "MAD"


def test_export_endpoint_returns_xlsx():
    pdf_bytes = _make_pdf(READY_TEXT)

    response = client.post(
        "/export?format=xlsx",
        files={
            "file": (
                "sample-invoice.pdf",
                pdf_bytes,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "sample-invoice.xlsx" in response.headers["content-disposition"]
    assert len(response.content) > 0

def test_export_endpoint_blocks_invoice_not_ready():
    pdf_bytes = _make_pdf("""
Invoice No: FAC-2026-001
Invoice Date: 2026-09-07
Total TTC: 1200 MAD
""")

    extract_response = client.post(
        "/extract",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert extract_response.status_code == 200
    extracted = extract_response.json()["data"]

    # Confirm this really is the gap being tested: every review_invoice
    # required field is present, but supplier_name was never extracted.
    assert extracted["invoice_number"] == "FAC-2026-001"
    assert extracted["supplier_name"] is None

    response = client.post(
        "/export?format=csv&filename=invoice",
        json=extracted,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(
        error.get("loc", [])[-1] == "supplier_name" for error in detail
    ), f"expected a supplier_name validation error, got: {detail}"


#===================================================
# PDF text extraction with error Handling
#===================================================
def test_export_endpoint_returns_csv():
    pdf_bytes = _make_pdf(READY_TEXT)

    extract_response = client.post(
        "/extract",
        files={"file": ("sample-invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert extract_response.status_code == 200
    extracted = extract_response.json()["data"]

    response = client.post(
        "/export?format=csv&filename=sample-invoice",
        json=extracted,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "sample-invoice.csv" in response.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1

    row = rows[0]
    assert row["invoice_number"] == "2026/145"
    assert row["invoice_date"] == "2026-09-05"
    assert row["supplier_name"] == "ACME SARL"
    assert row["total_amount"] == "1200"
    assert row["currency"] == "MAD"


def test_export_endpoint_returns_xlsx():
    pdf_bytes = _make_pdf(READY_TEXT)

    extract_response = client.post(
        "/extract",
        files={"file": ("sample-invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert extract_response.status_code == 200
    extracted = extract_response.json()["data"]

    response = client.post(
        "/export?format=xlsx&filename=sample-invoice",
        json=extracted,
    )

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "sample-invoice.xlsx" in response.headers["content-disposition"]
    assert len(response.content) > 0

#=============================================================
# InvoicData test
#=============================================================

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

#===================================================================
# tests after pdf failures
#===================================================================

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

#==============================================================
# Regex regression tests
#==============================================================

def test_extract_tax_amount_when_totals_share_same_line():
    text = (
        "Total HT : 4 850,00 DH   "
        "TVA (20%) : 970,00 DH   "
        "Total TTC : 5 820,00 DH"
    )

    assert extract_tax_amount(text) == Decimal("970.00")


def test_extract_total_amount_when_totals_share_same_line():
    text = (
        "Total HT : 4 850,00 DH   "
        "TVA (20%) : 970,00 DH   "
        "Total TTC : 5 820,00 DH"
    )

    assert extract_total_amount(text) == Decimal("5820.00")

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
    text = (
        "Émetteur : Adressé à :\n"
        "VOTRE SOCIÉTÉ SARL\n"
        "CLIENT EXEMPLE SARL\n"
    )

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

def test_extract_subtotal_amount_when_value_is_on_next_line():
    text = (
        "Total HT\n"
        "9 200,00\n"
    )

    assert extract_subtotal_amount(text) == Decimal("9200.00")


def test_extract_tax_amount_when_value_is_on_next_line_after_rate():
    text = (
        "Total TVA 20%\n"
        "1 840,00\n"
    )

    assert extract_tax_amount(text) == Decimal("1840.00")


def test_extract_total_amount_when_value_is_on_next_line():
    text = (
        "Total TTC\n"
        "11 040,00\n"
    )

    assert extract_total_amount(text) == Decimal("11040.00")

def test_extract_invoice_number_from_ref_label():
    text = (
        "Facture\n"
        "Réf. : FA-2026-001\n"
        "Date : 12/09/2026\n"
    )

    assert extract_invoice_number(text) == "FA-2026-001"

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