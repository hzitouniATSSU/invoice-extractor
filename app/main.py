import shutil
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

from app.exporters import export_invoice_to_csv, export_invoice_to_excel
from app.filenames import sanitize_filename_stem
from app.models import InvoiceData
from app.pdf import read_pdf_text
from app.pipeline import extract_invoice
from app.review import review_invoice, validate_invoice_data

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
async def upload_page():
    return FileResponse(STATIC_DIR / "index.html")



@app.post("/extract")
async def extract_invoice_endpoint(file: UploadFile = File(...)):
    text = await read_pdf_text(file)

    extraction = extract_invoice(text)
    review = review_invoice(extraction)

    return{
            "filename": file.filename,
            "status": review.status,
            "data": review.data,
            "issues": review.issues,}

EXPORTERS ={
    "csv": (
        export_invoice_to_csv, 
        "text/csv",
        ),
    "xlsx":(
        export_invoice_to_excel, 
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
}

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
    safe_filename = sanitize_filename_stem(filename)
    download_filename = f"{safe_filename}.{format}"
 
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