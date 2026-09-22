import re
from datetime import date, datetime

from app.models import CurrencyResult

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