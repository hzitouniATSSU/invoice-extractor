import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl

from app.models import InvoiceData




def export_invoice_to_csv(invoice: InvoiceData, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = invoice.model_dump()
    fieldnames= list(data.keys())

    row = {}
    for key, value in data.items():
        if value is None:
            row[key] = ""
        elif isinstance(value, Decimal):
            row[key] = str(value)
        elif isinstance(value, date):
            row[key] = value.isoformat()
        else:
            row[key] = value

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)

    return output_path

def export_invoice_to_excel(invoice: InvoiceData, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = invoice.model_dump()
    fieldnames = list(data.keys())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoice"

    ws.append(fieldnames)
    row = []

    for key in fieldnames:
        value = data[key]

        if isinstance(value, Decimal):
            row.append(float(value))
        else:
            row.append(value)

    ws.append(row)

    for col_idx, key in enumerate(fieldnames, start=1):
        if isinstance(data[key], date):
            ws.cell(row=2, column=col_idx).number_format="YYYY-MM-DD"

    wb.save(output_path)
    return output_path