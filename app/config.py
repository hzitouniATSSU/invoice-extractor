import os

APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_PDF_SIZE_MB = int(os.getenv("MAX_PDF_SIZE_MB", "10"))

if MAX_PDF_SIZE_MB <= 0:
    raise ValueError("MAX_PDF_SIZE_MB must be greater than 0.")
