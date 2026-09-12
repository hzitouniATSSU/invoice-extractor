import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import openpyxl 
from app.models import InvoiceData, ExtractedInvoiceData, ReviewIssue,ReviewResult, CurrencyResult, ExtractionResult,TaxIdResult

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

TOTAL_PATTERN = re.compile(
    r"""
    (?:^|[ \t]{2,})
    (?:
        total[ \t]*ttc
        |
        montant[ \t]*ttc
        |
        total
    )
    [ \t]*:?[ \t]*
    (?P<value>\d[\d .,]*\d|\d)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)
TOTAL_NEXT_LINE_PATTERN = re.compile(
    r"""
    ^[ \t]*
    (?:
        Total[ \t]*TTC
        |
        Montant[ \t]*TTC
        |
        Total
    )
    [ \t]*:?[ \t]*
    $
    \n
    [ \t]*
    (?P<value>\d[\d .,]*\d|\d)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

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
EMETTEUR_SECTION_PATTERN = re.compile(
    r"""
    ^[ \t]*(?:ÉMETTEUR|EMETTEUR)[ \t]*$
    (?P<section>.*?)
    (?=
        ^[ \t]*(?:CLIENT|CUSTOMER|FOURNISSEUR|SUPPLIER)[ \t]*$
        |
        \Z
    )
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE | re.DOTALL,
)
GENERIC_ICE_PATTERN = re.compile(
    r"""
    I[.]?C[.]?E[.]?
    [ \t]*:[ \t]*
    (?P<value>\d{15})
    """,
    re.IGNORECASE | re.VERBOSE,
)
PARTY_MAP = {
    "client": "customer",
    "customer": "customer",
    "fournisseur": "supplier",
    "supplier": "supplier",
}
TAX_ID_LABEL_ALTS = r"ICE|IF|Identifiant[ \t]*Fiscal|Tax[ \t]*ID"

COMBINED_TAX_ID_PATTERN = re.compile(
    rf"""
    ^[ \t]*
    (?:
        (?P<party_before>Client|Customer|Fournisseur|Supplier)[ \t]*(?P<label_before>{TAX_ID_LABEL_ALTS})
        |
        (?P<label_after>{TAX_ID_LABEL_ALTS})[ \t]*(?P<party_after>Client|Customer|Fournisseur|Supplier)
    )
    [ \t]*[:\-]?[ \t]*
    (?P<value>[^\n\s:\-][^\n]*)
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

CUSTOMER_ICE_CONTEXT_PATTERN = re.compile(
    r"""
    ^[ \t]*
    CLIENT[ \t]+[^\n]+
    [ \t]*$
    \n
    [ \t]*
    I[.]?C[.]?E[.]?
    [ \t]*:[ \t]*
    (?P<value>\d{15})
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

SUBTOTAL_PATTERN = re.compile(
    r"""
    ^[ \t]*
    (?:
        Sous[ \t\-]*total
        |
        subtotal
        |
        Total[ \t]+HT
    )
    \b
    [ \t]*[:\-]?[ \t]*
    (?P<value>\d[\d .,]*\d|\d)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

SUBTOTAL_NEXT_LINE_PATTERN = re.compile(
    r"""
    ^[ \t]*
    (?:
        Sous[ \t\-]*total
        |
        subtotal
        |
        Total[ \t]+HT
    )
    [ \t]*:?[ \t]*
    $
    \n
    [ \t]*
    (?P<value>\d[\d .,]*\d|\d)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

TAX_AMOUNT_PATTERN = re.compile(
    r"""
    (?:^|[ \t]{2,})
    (?:
        Total[ \t]+TVA
        |
        TVA
        |
        VAT
        |
        Tax[ \t]*Amount
        |
        Tax
    )
    \b

    [ \t]*

    (?:
        \(?[ \t]*
        \d+(?:[.,]\d+)?
        [ \t]*%
        [ \t]*\)?
    )?

    [ \t]*[:\-]?[ \t]*

    (?P<value>\d[\d .,]*\d|\d)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

TAX_AMOUNT_NEXT_LINE_PATTERN = re.compile(
    r"""
    ^[ \t]*
    (?:
        Total[ \t]+TVA
        |
        TVA
        |
        VAT
        |
        Tax[ \t]*Amount
        |
        Tax
    )
    \b
    [ \t]*
    (?:
        \(?[ \t]*
        \d+(?:[.,]\d+)?
        [ \t]*%
        [ \t]*\)?
    )?
    [ \t]*:?[ \t]*
    $
    \n
    [ \t]*
    (?P<value>\d[\d .,]*\d|\d)
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

SUPPLIER_FOOTER_ICE_PATTERN = re.compile(
    r"""
    ^[ \t]*
    Si[eè]ge[ \t]+social
    [ \t]*:
    [^\n]+
    $
    (?:
        \n[^\n]*
    ){0,2}
    \n?
    [^\n]*
    I[.]?C[.]?E[.]?
    [ \t]*:[ \t]*
    (?P<value>\d{15})
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
    
   
def _valid_grouping(number_part: str, sep: str) -> bool:
    """ True if splitting on `sep` looks like real thousands grouping:
    first group 1-3 digits, every subsequent group exactly 3 digits."""
    groups = number_part.split(sep)
    if len(groups) < 2:
        return True
    if not (1<= len(groups[0])<=3):
        return False
    return all(len(g) == 3 for g in groups[1:])

def normalize_amount(raw: str) -> Decimal | None:
    if raw is None:
        return None

    text = raw.strip().replace(" ", "")
    if not text:
        return None

    has_comma= "," in text
    has_dot ="." in text

    if has_comma and has_dot:
        if text.rfind(",") > text.rfind("."):
            decimal_sep, thousands_sep= ",","."
        else:
            decimal_sep, thousands_sep= ".",","

        integer_part = text.split(decimal_sep)[0]
        if not _valid_grouping(integer_part, thousands_sep):
            return None

        text = text.replace(thousands_sep, "")
        if decimal_sep == ",":
            text = text.replace(",", ".")

    elif has_comma:
        if text.count(",")>1:
            if not _valid_grouping(text, ","):
                return None
            text = text.replace(",","")
        else:
            digits_after = len(text.split(",")[-1])
            if digits_after == 3:
                text = text.replace(",", "")
            else:
                text = text.replace(",", ".")

    elif has_dot:
        if text.count(".") > 1:
            if not _valid_grouping(text, "."):
                return None
            text = text.replace(".", "")
        else:
            digits_after = len(text.split(".")[-1])
            if digits_after == 3:
                text = text.replace(".", "")

    try:
        return Decimal(text)
    except InvalidOperation:
        return None

def extract_total_amount(text: str) -> Decimal | None:
    match = TOTAL_NEXT_LINE_PATTERN.search(text)
    if not match:
        match = TOTAL_PATTERN.search(text)
    if not match:
        return None
    return normalize_amount(match.group("value"))



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


def _canonical_label(raw_label: str) -> str:
    return re.sub(r"\s+", " ", raw_label.strip()).upper()

def extract_tax_id_by_party(text: str) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {}
    for match in COMBINED_TAX_ID_PATTERN.finditer(text):
        party_word = match.group("party_before") or match.group("party_after")
        label_word = match.group("label_before") or match.group("label_after")
        party = PARTY_MAP[party_word.strip().lower()]
        label = _canonical_label(label_word)
        value = match.group("value").strip()
        if not value:
            continue
        result.setdefault(party, []).append((label, value))    

    return result


SUPPLIER_TAX_ID_PRIORITY = ["ICE", "IF", "IDENTIFIANT FISCAL", "TAX ID"]
def _distinct_values_for_label(entries: list[tuple[str, str]], wanted_label: str) -> set[str]:
    return {value for label, value in entries if label == wanted_label}


def _select_customer_ice(entries: list[tuple[str, str]]) -> str | None:
    values = _distinct_values_for_label(entries, "ICE")
    if len(values) == 1:
        return values.pop()
    return None

    

def _select_supplier_tax_id(entries: list[tuple[str, str]]) -> str | None:
    for wanted_label in SUPPLIER_TAX_ID_PRIORITY:
        values = _distinct_values_for_label(entries, wanted_label)
        if len(values) == 1:
            return values.pop()
        if len(values) > 1:
            return None

    return None

def extract_customer_ice_from_context(text: str) -> TaxIdResult:
    matches = CUSTOMER_ICE_CONTEXT_PATTERN.finditer(text)

    values = {
        match.group("value").strip()
        for match in matches
    }

    if len(values) == 1:
        return TaxIdResult.found("ICE", values.pop())

    if len(values) > 1:
        return TaxIdResult.conflicting("ICE", values)

    return TaxIdResult.missing()

def extract_supplier_ice_from_emetteur_section(text: str) -> TaxIdResult:
    section_match = EMETTEUR_SECTION_PATTERN.search(text)

    if not section_match:
        return TaxIdResult.missing()

    section = section_match.group("section")

    values = {
        match.group("value").strip()
        for match in GENERIC_ICE_PATTERN.finditer(section)
    }

    if len(values) == 1:
        return TaxIdResult.found("ICE", values.pop())

    if len(values) > 1:
        return TaxIdResult.conflicting("ICE", values)

    return TaxIdResult.missing()
            
def extract_subtotal_amount(text: str) -> Decimal | None:
    match = SUBTOTAL_NEXT_LINE_PATTERN.search(text)
    if not match:
        match = SUBTOTAL_PATTERN.search(text)
    if not match:
        return None
    return normalize_amount(match.group("value"))


def extract_tax_amount(text: str) -> Decimal | None:
    match = TAX_AMOUNT_NEXT_LINE_PATTERN.search(text)

    if not match:
        match = TAX_AMOUNT_PATTERN.search(text)
    if not match:
        return None
    return normalize_amount(match.group("value"))




def is_totals_consistent(
    subtotal: Decimal | None,
    tax_amount: Decimal | None,
    total_amount: Decimal | None,
) -> bool | None:
    """Checks subtotal + tax_amount == total_amount. Returns None (not
    "consistent") when any of the three is missing -- there isn't enough
    information to validate, which is a different situation from an actual
    mismatch. A caller can use False as the signal to raise a manual-review
    flag; None just means "nothing to check yet"."""
    if subtotal is None or tax_amount is None or total_amount is None:
        return None
    return subtotal + tax_amount == total_amount


def review_invoice(extraction: "ExtractionResult") -> ReviewResult:
    data = extraction.data
    currency_result = extraction.currency_result
    customer_ice_result = extraction.customer_ice_result
    supplier_tax_id_result = extraction.supplier_tax_id_result
    issues: list[ReviewIssue] = []

    if data.invoice_number is None:
        issues.append(ReviewIssue(field="invoice_number", code="missing_required_field",
                                   message="Invoice number is missing.", severity="error"))
    if data.invoice_date is None:
        issues.append(ReviewIssue(field="invoice_date", code="missing_required_field",
                                   message="Invoice date is missing.", severity="error"))
    if data.total_amount is None:
        issues.append(ReviewIssue(field="total_amount", code="missing_required_field",
                                   message="Total amount is missing.", severity="error"))

    if currency_result.status == "missing":
        issues.append(ReviewIssue(field="currency", code="missing_required_field",
                                   message="No currency detected", severity="error"))
    elif currency_result.status == "conflicting":
        issues.append(ReviewIssue(field="currency", code="conflicting_currency",
                                   message=f"Multiple currencies detected: {', '.join(sorted(currency_result.candidates))}.",
                                   severity="error"))

    customer_ice_result = customer_ice_result
    if customer_ice_result.status == "found" and not is_valid_ice(customer_ice_result.value):
        issues.append(ReviewIssue(field="customer_ICE", code="invalid_ice", message="Customer ICE must contain 15 digits.", severity="warning"))
    elif customer_ice_result.status == "conflicting":
        issues.append(ReviewIssue(field="customer_ICE", code="conflicting_ice", message=(f"Multiple customer {customer_ice_result.label} values "f"detected: {', '.join(sorted(customer_ice_result.candidates))}."),severity="warning"))

    supplier_tax_id_result = supplier_tax_id_result
    if supplier_tax_id_result.status == "conflicting":
        issues.append(ReviewIssue(field="supplier_tax_id", code="conflicting_tax_id", message=(f"Multiple supplier {supplier_tax_id_result.label} values " f"detected: {', '.join(sorted(supplier_tax_id_result.candidates))}."),severity="warning"))

    totals_ok = is_totals_consistent(data.subtotal, data.tax_amount, data.total_amount)
    if totals_ok is False:
        issues.append(ReviewIssue(field="total_amount", code="inconsistent_totals",message="Subtotal + tax amount does not equal total amount.", severity="warning"))

    if data.supplier_name is None:
        issues.append(
            ReviewIssue(
                field="supplier_name",
                code="missing_required_field",
                message="Supplier name is missing.",
                severity="error",
            )
        )

    return ReviewResult(data=data, issues=issues)

def _select_supplier_tax_id_result(entries: list[tuple[str, str]]) -> TaxIdResult:
    for wanted_label in SUPPLIER_TAX_ID_PRIORITY:
        values = _distinct_values_for_label(entries, wanted_label)
        if len(values) == 1:
            return TaxIdResult.found(wanted_label, values.pop())
        if len(values)> 1:
            return TaxIdResult.conflicting(wanted_label, values)
    return TaxIdResult.missing()

def extract_supplier_ice_from_footer(text: str) -> TaxIdResult:
    values = {
        match.group("value").strip()
        for match in SUPPLIER_FOOTER_ICE_PATTERN.finditer(text)
    }

    if len(values) == 1:
        return TaxIdResult.found("ICE", values.pop())

    if len(values) > 1:
        return TaxIdResult.conflicting("ICE", values)

    return TaxIdResult.missing()

def _select_customer_ice_result(
    entries: list[tuple[str, str]],
) -> TaxIdResult:
    values = _distinct_values_for_label(entries, "ICE")
    if len(values) == 1:
        return TaxIdResult.found("ICE", values.pop())
    if len(values) > 1:
        return TaxIdResult.conflicting("ICE", values)
    return TaxIdResult.missing()



def extract_invoice(text: str) -> ExtractionResult:
    currency_result = extract_currency(text)
   
    tax_ids_by_party = extract_tax_id_by_party(text)
    customer_entries = tax_ids_by_party.get("customer", [])
    supplier_entries = tax_ids_by_party.get("supplier", [])

    customer_ice_result = _select_customer_ice_result(customer_entries)
    if customer_ice_result.status == "missing":
       customer_ice_result = extract_customer_ice_from_context(text)
    supplier_tax_id_result = _select_supplier_tax_id_result(supplier_entries)
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


class InvoiceNotReadyError(Exception):
    def __init__(self, status: str, issues: list[ReviewIssue]):
        self.status = status
        self.issues = issues
        summary = "; ".join(f"{i.field}:{i.code}" for i in issues) or "no issues listed"
        super().__init__(f"Cannot finalize invoice: review status is '{status}', not 'ready'. Issues: {summary}")


def finalize_invoice(extraction: ExtractionResult, review: ReviewResult) -> InvoiceData:
    if review.status != "ready":
        raise InvoiceNotReadyError(review.status, review.issues)

    data = extraction.data
    return InvoiceData(
        invoice_number=data.invoice_number,
        invoice_date=data.invoice_date,
        total_amount=data.total_amount,
        currency=data.currency,
        supplier_name=data.supplier_name,
        customer_name=data.customer_name,
        customer_ICE=data.customer_ICE,
        supplier_tax_id=data.supplier_tax_id,
        subtotal=data.subtotal,
        tax_amount=data.tax_amount,
    )

