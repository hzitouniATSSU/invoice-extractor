
from app.models import ExtractedInvoiceData, ExtractionResult
from app.tax_ids import (
    extract_tax_id_by_party,
    extract_customer_ice_from_context,
    extract_supplier_ice_from_footer,
    extract_supplier_ice_from_emetteur_section,
    select_customer_ice_result,
    select_supplier_tax_id_result,
)
from app.amounts import (
    extract_subtotal_amount,
    extract_tax_amount,
    extract_total_amount,
)
from app.parties import (
    extract_customer_name,
    extract_supplier_name

)
from app.fields import (
    extract_currency,
    extract_invoice_date,
    extract_invoice_number,
)


def extract_invoice(text: str) -> ExtractionResult:
    currency_result = extract_currency(text)
   
    tax_ids_by_party = extract_tax_id_by_party(text)
    customer_entries = tax_ids_by_party.get("customer", [])
    supplier_entries = tax_ids_by_party.get("supplier", [])

    customer_ice_result = select_customer_ice_result(customer_entries)
    if customer_ice_result.status == "missing":
       customer_ice_result = extract_customer_ice_from_context(text)
    supplier_tax_id_result = select_supplier_tax_id_result(supplier_entries)
    if supplier_tax_id_result.status == "missing":
        supplier_tax_id_result = extract_supplier_ice_from_footer(text)
    if supplier_tax_id_result.status == "missing":
       supplier_tax_id_result = extract_supplier_ice_from_emetteur_section(text)


    currency = currency_result.value if currency_result.status == "found" else None
    customer_ICE = (
        customer_ice_result.value
        if customer_ice_result.status == "found"
        else None
    )
    supplier_tax_id = (
        supplier_tax_id_result.value
        if supplier_tax_id_result.status == "found"
        else None
    )

    data = ExtractedInvoiceData(
        invoice_date = extract_invoice_date(text),
        invoice_number = extract_invoice_number(text),
        total_amount = extract_total_amount(text),
        currency = currency,
        supplier_name = extract_supplier_name(text),
        customer_name = extract_customer_name(text),
        customer_ICE = customer_ICE,
        supplier_tax_id = supplier_tax_id,
        subtotal = extract_subtotal_amount(text),
        tax_amount = extract_tax_amount(text),
    )

    

    return ExtractionResult(
        currency_result=currency_result,
        data=data,
        customer_ice_result=customer_ice_result,
        supplier_tax_id_result=supplier_tax_id_result

    )

def extract_invoice_data(text: str) -> ExtractedInvoiceData:
    return extract_invoice(text).data




