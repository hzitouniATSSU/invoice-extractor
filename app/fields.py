import re
from datetime import date, datetime

from app.models import CurrencyResult

# Dots are allowed inside a number ("2026.0045") but never at its end, so a
# sentence-final period is not captured.
INVOICE_NUMBER_VALUE = r"""
    [ \t]*[:\-]?[ \t]*
    (?P<number>
        (?=[A-Za-z0-9/_.-]*\d)
        [A-Za-z0-9]
        (?:[A-Za-z0-9/_-]|\.(?=[A-Za-z0-9]))*
    )
"""

INVOICE_PATTERN = re.compile(
    r"""
    (?:
    invoice[ \t]*n[°o]\.?
    |
    invoice[ \t]*number
    |
    invoice[ \t]*\#
    |
    facture[ \t]*n[°o]
    |
    n[°o][ \t]*(?:de[ \t]+)?facture
    |
    num[ée]ro[ \t]+de[ \t]+facture
    )
    """
    + INVOICE_NUMBER_VALUE,
    re.IGNORECASE | re.VERBOSE,
)

# "Réf" is also used for purchase-order and quote references, so it is only
# a fallback when no explicit invoice-number label is present.
REFERENCE_PATTERN = re.compile(
    r"""
    réf[ \t]*\.?
    """
    + INVOICE_NUMBER_VALUE,
    re.IGNORECASE | re.VERBOSE,
)


DATE_VALUE = r"""
    [ \t]*[:\-]?[ \t]*
    (?P<value>\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4})
"""

INVOICE_DATE_PATTERN = re.compile(
    r"""
    (?:
    invoice[ \t]*date
    |
    issue[ \t]*date
    |
    date[ \t]*de[ \t]*facture
    |
    date[ \t]*facture
    |
    facture[ \t]*du
    )
    """
    + DATE_VALUE,
    re.IGNORECASE | re.VERBOSE,
)

# A bare "Date" label, used only when no explicit invoice-date label exists.
# A word directly before it ("Due Date", "Order Date", "Delivery Date")
# qualifies it as some other date, so it is skipped. Two or more spaces are
# a column gap, not a qualifier.
BARE_DATE_PATTERN = re.compile(
    r"""
    (?<![^\W\d_][ \t])
    \bdate
    """
    + DATE_VALUE,
    re.IGNORECASE | re.VERBOSE,
)

DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
]


CURRENCY_CODE_PATTERN = re.compile(r"\b(?:MAD|DHS?|EUR|USD|CAD|AUD)\b", re.IGNORECASE)

CURRENCY_SYMBOL_PATTERN = re.compile(r"[$€£¥]")

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
    match = INVOICE_PATTERN.search(text) or REFERENCE_PATTERN.search(text)
    if match:
        return match.group("number")
    return None


def extract_invoice_date(text: str) -> date | None:
    match = INVOICE_DATE_PATTERN.search(text) or BARE_DATE_PATTERN.search(text)
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
