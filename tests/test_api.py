import  csv, openpyxl
from fastapi.testclient import TestClient
from app.main import app
import io

client = TestClient(app)



from io import BytesIO
from reportlab.pdfgen import canvas



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

READY_TEXT = (
    "Facture N° 2026/145\n"
    "Date de facture: 05/09/2026\n"
    "Subtotal: 1000 MAD\n"
    "Supplier: ACME SARL\n"
    "TVA: 200 MAD\n"
    "Total TTC: 1200 MAD\n"
    "Currency: MAD"
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
