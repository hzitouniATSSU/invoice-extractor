import re
from datetime import date, datetime

from app.models import ExtractedInvoiceData, CurrencyResult, ExtractionResult,TaxIdResult
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


INVOICE_PATTERN= re.compile(
    r"""
    (?:
    invoice[ \t]*no\.?
    |
    invoice[ \t]*number
    |
    facture[ \t]*n[°o]
    |
    n[°o][ \t]*facture
    |
    réf[ \t]*\.?
    )
    [ \t]*[:\-]?[ \t]*
    (?P<number>(?=[A-Za-z0-9/_-]*\d)[A-Za-z0-9][A-Za-z0-9/_-]*)
    """,
    re.IGNORECASE | re.VERBOSE,
)


DATE_PATTERN = re.compile(
    r"""
    (?:
    invoice[ \t]*date
    |
    date[ \t]*de[ \t]*facture
    |
    date[ \t]*facture
    |
    date
    |
    facture[ \t]*du
    )
    [ \t]*[:\-]?[ \t]*
    (?P<value>\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4})
""",
re.IGNORECASE | re.VERBOSE
)

DATE_FORMATS =[
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
]


CURRENCY_CODE_PATTERN = re.compile(
r'\b(?:MAD|DHS?|EUR|USD|CAD|AUD)\b',
 re.IGNORECASE 
)

CURRENCY_SYMBOL_PATTERN = re.compile(
 r'[$€£¥]'
)

CODE_TO_CANONICAL = {
    "MAD": "MAD",
    "DH": "MAD",
    "DHS": "MAD",
    "EUR": "EUR",
    "USD": "USD",
    "CAD": "CAD",
    "AUD": "AUD",
}

SYMBOL_TO_CANONICAL = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}

SUPPLIER_PATTERN = re.compile(
    r"""
    ^[ \t]*
    (?:supplier|fournisseur|vendor)
    (?![ \t]*[:\-]?[ \t]*(?:ICE|IF|Identifiant[ \t]*Fiscal|Tax[ \t]*ID)\b)
    [ \t]*[:\-]?[ \t]*
    (?P<name>[^\n\s:\-][^\n]*)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)
SUPPLIER_SECTION_PATTERN = re.compile(
    r"""
    ^[ \t]*
    (?:ÉMETTEUR|EMETTEUR)
    [ \t]*
    $
    [ \t]*\n
    [ \t]*
    (?P<name>[^\n]+)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

SUPPLIER_TWO_COLUMN_PATTERN = re.compile(
    r"""
    ^[ \t]*Émetteur[ \t]*:[ \t]*$
    [ \t]*\n
    ^[ \t]*Adressé[ \t]+à[ \t]*:[ \t]*$
    [ \t]*\n
    ^[ \t]*(?P<name>[^\n]+)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)




CUSTOMER_PATTERN = re.compile(
    r"""
  ^[ \t]*
    (?:
        Customer
        |
        Client
        |
        Bill[ \t]*To
        |
        Factur[ée][ \t]*à
    )
    [ \t]*[:\-][ \t]*]*
    (?![ \t]*[:\-]?[ \t]*(?:ICE|IF|Identifiant[ \t]*Fiscal|Tax[ \t]*ID)\b)
    (?P<value>[^\n\s:\-][^\n]*)
""",
re.IGNORECASE | re.VERBOSE | re.MULTILINE
)

CUSTOMER_SECTION_PATTERN = re.compile(
    r"""
    ^[ \t]*
    CLIENT
    [ \t]*:?[ \t]*
    $
    [ \t]*\n
    [ \t]*
    (?P<name>[^\n]+)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

CUSTOMER_BEFORE_ICE_PATTERN = re.compile(
    r"""
    ^[ \t]*
    (?P<name>CLIENT[ \t]+[^\n:]+?)
    [ \t]*$
    \n
    [ \t]*
    I[.]?C[.]?E[.]?
    [ \t]*:
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)






def extract_invoice_number(text: str) -> str | None:
    match = INVOICE_PATTERN.search(text)
    if match:
        return match.group("number")
    return None


def extract_invoice_date(text: str) -> date | None:
    match = DATE_PATTERN.search(text)
    if not match: 
        return None

    raw = match.group("value")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    return None
    
   








def extract_currency(text: str) -> CurrencyResult:
    raw_codes = CURRENCY_CODE_PATTERN.findall(text)
    canonical_codes = {CODE_TO_CANONICAL[code.upper()] for code in raw_codes}

    raw_symbols = CURRENCY_SYMBOL_PATTERN.findall(text)
    canonical_symbols = {SYMBOL_TO_CANONICAL[symbol] for symbol in raw_symbols}

    combined = canonical_codes | canonical_symbols

    if len(combined) == 0:
        return CurrencyResult.missing()
    if len(combined) == 1: 
        return CurrencyResult.found(next(iter(combined)))
    return CurrencyResult.conflicting(combined)

def extract_supplier_name(text: str) -> str | None:
    match = SUPPLIER_PATTERN.search(text)

    if match:
        name = match.group("name").strip().lstrip(":-").strip()
        return name or None

    match = SUPPLIER_SECTION_PATTERN.search(text)

    if match:
        name = match.group("name").strip()
        return name or None

    match = SUPPLIER_TWO_COLUMN_PATTERN.search(text)

    if match:
        name = match.group("name").strip()
        return name or None

    return None


def is_ice_label(label: str) -> bool:
    return label.strip().upper() == "ICE"


def is_valid_ice(value: str) -> bool:
    """ICE numbers are 15 digits. Strips formatting characters we
    explicitly allow (currently just spaces, per the "001 234 567 000 089"
    grouping style) before checking length/digit-only."""
    cleaned = value.replace(" ", "")
    return bool(re.fullmatch(r"\d{15}", cleaned))


def extract_customer_name(text: str) -> str | None:
    match = CUSTOMER_PATTERN.search(text)

    if match:
        value = match.group("value").strip()
        return value or None

    match = CUSTOMER_SECTION_PATTERN.search(text)

    if match:
        value = match.group("name").strip()
        return value or None

    match = CUSTOMER_BEFORE_ICE_PATTERN.search(text)

    if match:
        value = match.group("name").strip()
        return value or None

    return None

            






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



    if currency_result.status == "found":
        currency = currency_result.value
    else:
        currency = None

    if customer_ice_result.status == "found":
        customer_ICE = customer_ice_result.value
    else:
        customer_ICE = None

    if supplier_tax_id_result.status == "found":
        supplier_tax_id = supplier_tax_id_result.value
    else:
        supplier_tax_id = None

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




