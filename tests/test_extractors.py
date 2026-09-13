import pytest, csv, openpyxl
from pydantic import ValidationError
from datetime import date,datetime
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
import io

client = TestClient(app)

from app.pipeline import (
  extract_invoice_data,
    extract_invoice,
    
)

from app.exporters import export_invoice_to_csv, export_invoice_to_excel
from app.review import review_invoice, finalize_invoice, InvoiceNotReadyError,  is_totals_consistent
from app.tax_ids import extract_tax_id_by_party, select_customer_ice_result, select_supplier_tax_id_result, is_valid_ice
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




# ============================================================
# Invoice date
# ============================================================




# ============================================================
# Amount normalization
# ============================================================




# ============================================================
# Total
# ============================================================




# ============================================================
# Subtotal
# ============================================================




# ============================================================
# Tax amount
# ============================================================




# ============================================================
# Currency
# ============================================================



# ============================================================
# Supplier / customer names
# ============================================================




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


#==============================================================
# Regex regression tests
#==============================================================




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