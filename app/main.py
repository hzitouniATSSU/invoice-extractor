import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

from app.exporters import export_invoice_to_csv, export_invoice_to_excel
from app.filenames import sanitize_filename_stem
from app.logging_config import configure_logging
from app.models import InvoiceData
from app.pdf import read_pdf_text
from app.pipeline import extract_invoice
from app.review import review_invoice, validate_invoice_data

configure_logging()
app = FastAPI()

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
async def upload_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/extract")
async def extract_invoice_endpoint(file: UploadFile = File(...)):
    request_id = str(uuid.uuid4())
    logger.info(
        "Extraction request received request_id=%s content_type=%s",
        request_id,
        file.content_type,
    )
    try:
        text = await read_pdf_text(file)
    except HTTPException as exc:
        logger.warning(
            "PDF rejected request_id=%s status_code=%s", request_id, exc.status_code
        )
        raise
    extraction = extract_invoice(text)
    review = review_invoice(extraction)
    logger.info(
        "Extraction completed request_id=%s review_status=%s", request_id, review.status
    )
    return {
        "filename": file.filename,
        "status": review.status,
        "data": review.data,
        "issues": review.issues,
    }


EXPORTERS = {
    "csv": (
        export_invoice_to_csv,
        "text/csv",
    ),
    "xlsx": (
        export_invoice_to_excel,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
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
            detail="Failed to generate export file",
        ) from e

    cleanup = BackgroundTask(shutil.rmtree, tmp_dir, ignore_errors=True)

    return FileResponse(
        path=created_path,
        filename=download_filename,
        media_type=media_type,
        background=cleanup,
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}
