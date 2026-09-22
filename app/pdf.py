import io

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, ParseError, PdfReadError

MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024


async def read_pdf_text(file: UploadFile) -> str:
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF files are allowed.",
        )

    contents = await file.read(MAX_PDF_SIZE_BYTES + 1)
    if len(contents) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="PDF exceeds the 10 MB limit.",
        )

    try:
        pdf = PdfReader(io.BytesIO(contents))
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    except FileNotDecryptedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password-protected or encrypted PDFs are not supported.",
        )

    except (PdfReadError, ParseError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or invalid PDF file structure.",
        )

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No extractable text found. Scanned PDFs are not supported in this version.",
        )

    return text
