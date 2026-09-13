from fastapi import  UploadFile, HTTPException, status
from pypdf import PdfReader
from pypdf.errors import PdfStreamError
import io



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