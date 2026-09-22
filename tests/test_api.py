import csv
import io
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from app.main import app
from app.pdf import MAX_PDF_SIZE_BYTES

client = TestClient(app)


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
        "No extractable text found. Scanned PDFs are not supported in this version."
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
VALID_INVOICE = {
    "invoice_number": "2026/145",
    "invoice_date": "2026-09-05",
    "supplier_name": "ACME SARL",
    "supplier_tax_id": None,
    "customer_name": None,
    "customer_ICE": None,
    "subtotal": "1000",
    "tax_amount": "200",
    "total_amount": "1200",
    "currency": "MAD",
}


def test_export_endpoint_returns_csv():
    response = client.post(
        "/export?format=csv&filename=sample-invoice",
        json=VALID_INVOICE,
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
    response = client.post(
        "/export?format=xlsx&filename=sample-invoice",
        json=VALID_INVOICE,
    )

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "sample-invoice.xlsx" in response.headers["content-disposition"]
    assert len(response.content) > 0


def test_export_rejects_unsupported_currency_natively():
    payload = {**VALID_INVOICE, "currency": "XYZ"}
    response = client.post("/export?format=csv", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_export_rejects_blank_supplier_name_natively():
    payload = {**VALID_INVOICE, "supplier_name": "   "}
    response = client.post("/export?format=csv", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


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
    assert any(error.get("loc", [])[-1] == "supplier_name" for error in detail), (
        f"expected a supplier_name validation error, got: {detail}"
    )


# ===================================================
# PDF text extraction with error Handling
# ===================================================
def test_extract_then_export_csv():
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


def test_extract_then_export_xlsx():
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


def test_export_sanitizes_filename_from_query_param():
    # Otherwise-valid, fully corrected invoice -- the only thing under
    # test here is what /export does with a malicious `filename` query
    # param, not extraction or business-rule validation.
    valid_invoice = {
        "invoice_number": "FAC-2026-001",
        "invoice_date": "2026-09-07",
        "total_amount": "1200",
        "currency": "MAD",
        "supplier_name": "Atlas Trading Co.",
        "customer_name": None,
        "customer_ICE": None,
        "supplier_tax_id": None,
        "subtotal": "1000",
        "tax_amount": "200",
    }

    response = client.post(
        "/export",
        params={"format": "csv", "filename": "../../secret"},
        json=valid_invoice,
    )

    assert response.status_code == 200

    content_disposition = response.headers["content-disposition"]

    # This is the point of the test: prove the ENDPOINT calls
    # sanitize_filename_stem, not just that the helper works when called
    # directly. If someone ever removed the sanitize_filename_stem(...)
    # call from main.py and used the raw filename param instead, this
    # is what would catch it.
    assert 'filename="secret.csv"' in content_disposition
    assert ".." not in content_disposition
    assert "/" not in content_disposition


def test_extract_rejects_oversized_upload():
    # Doesn't need to be a real PDF: size validation happens before
    # PdfReader ever sees the bytes, so garbage content is fine here --
    # and using garbage (not a real 10MB+ PDF) is itself part of what
    # this test proves: the 413 must fire on size alone, before any
    # attempt to parse the content.
    oversized = b"x" * (MAX_PDF_SIZE_BYTES + 1)

    response = client.post(
        "/extract",
        files={"file": ("huge.pdf", oversized, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "PDF exceeds the 10 MB limit."


def test_extract_accepts_small_valid_pdf():
    pdf_bytes = _make_pdf(READY_TEXT)

    response = client.post(
        "/extract",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_extract_rejects_non_pdf_content_type():
    response = client.post(
        "/extract",
        files={"file": ("invoice.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file type. Only PDF files are allowed."


def test_extract_rejects_corrupt_pdf():
    response = client.post(
        "/extract",
        files={
            "file": ("invoice.pdf", b"not actually a pdf structure", "application/pdf")
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Corrupted or invalid PDF file structure."


def test_extract_rejects_pdf_with_no_extractable_text():
    pdf_bytes = _make_pdf("")

    response = client.post(
        "/extract",
        files={"file": ("blank.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "No extractable text found. Scanned PDFs are not supported in this version."
    )


def test_extract_rejects_encrypted_pdf():
    buffer = BytesIO()

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    writer.write(buffer)

    response = client.post(
        "/extract",
        files={
            "file": (
                "encrypted.pdf",
                buffer.getvalue(),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Password-protected or encrypted PDFs are not supported."
    )


def test_blocked_invoice_can_be_corrected_and_exported():
    pdf_bytes = _make_pdf("""
Invoice No: FAC-015
Invoice Date: 2026-08-29
Subtotal: 600 MAD
Tax: 120 MAD
Total TTC: 720 MAD
Customer: Mint Cafe
""")

    extract_response = client.post(
        "/extract",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )

    assert extract_response.status_code == 200

    payload = extract_response.json()
    assert payload["status"] == "blocked"
    assert payload["data"]["supplier_name"] is None

    corrected = payload["data"]
    corrected["supplier_name"] = "ACME SARL"

    export_response = client.post(
        "/export?format=csv&filename=corrected-invoice",
        json=corrected,
    )

    assert export_response.status_code == 200

    rows = list(csv.DictReader(io.StringIO(export_response.text)))
    assert len(rows) == 1
    assert rows[0]["supplier_name"] == "ACME SARL"
