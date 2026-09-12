from fastapi import FastAPI, UploadFile, File, HTTPException, status,Query
from pypdf import PdfReader
from pypdf.errors import PdfStreamError
from fastapi.responses import FileResponse,HTMLResponse
from starlette.background import BackgroundTask
from app.extractors import extract_invoice
from app.exporters import export_invoice_to_csv, export_invoice_to_excel
from app.review import review_invoice, is_totals_consistent
from app.models import InvoiceData
from app.tax_ids import is_valid_ice
import shutil
import tempfile
from pathlib import Path
from typing import Literal
import io

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"

async def read_pdf_text(file: UploadFile) -> str:
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,    
            detail="Invalid file type. Only PDF files are allowed."
        )
    try:
        contents = await file.read()
        pdf = PdfReader(io.BytesIO(contents))

        text = "\n".join(page.extract_text() or "" for page in pdf.pages)


    except PdfStreamError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or invalid PDF file structure."
        )

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extractable text found. Scanned PDFs are not supported in this version."
        )

    return text


@app.get("/", response_class=HTMLResponse)
async def upload_page():
    return FileResponse(STATIC_DIR / "index.html")



@app.post("/extract")
async def extract_invoice_endpoint(file: UploadFile = File(...)):
    text = await read_pdf_text(file)

    extraction = extract_invoice(text)
    review = review_invoice(extraction)

    return{
            "filename":file.filename,
            "status": review.status,
            "data": review.data,
            "issues": review.issues,}

EXPORTERS ={
    "csv": (export_invoice_to_csv, "text/csv"),
    "xlsx":(export_invoice_to_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
}

def validate_invoice_data(invoice: InvoiceData) -> list[str]:
   
    problems = []
    if invoice.customer_ICE is not None and not is_valid_ice(invoice.customer_ICE):
        problems.append("Customer ICE must contain 15 digits.")
 
    totals_ok = is_totals_consistent(invoice.subtotal, invoice.tax_amount, invoice.total_amount)
    if totals_ok is False:
        problems.append("Subtotal + tax amount does not equal total amount.")
 
    return problems

@app.post("/export")
async def export_invoice_endpoint(
    invoice: InvoiceData,
    format: Literal["csv", "xlsx"] = Query(...),
    filename: str = Query("invoice"),
):
    problems = validate_invoice_data(invoice)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Corrected invoice failed validation.",
                "issues": problems,
            },
        )
 
    export_fn, media_type = EXPORTERS[format]
    download_filename = f"{filename}.{format}"
 
    tmp_dir = tempfile.mkdtemp()
    output_path = Path(tmp_dir) / download_filename
    try:
        created_path = export_fn(invoice, output_path)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate export file"
        ) from e
 
    cleanup = BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True)
 
    return FileResponse(
        path=created_path,
        filename=download_filename,
        media_type=media_type,
        background=cleanup,
    )