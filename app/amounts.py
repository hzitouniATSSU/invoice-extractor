import re
from decimal import Decimal, InvalidOperation

CURRENCY = r"(?:(?:MAD|DHS?|EUR|USD|CAD|AUD)(?!\w)|[$€£¥])"

# Optional currency in parentheses after a label: "Total TTC (DH) : 960,00".
CURRENCY_NOTE = rf"(?:[ \t]*\([ \t]*{CURRENCY}[ \t]*\))?"

# Optional currency written before the amount: "Total : $1,100.00".
AMOUNT = rf"(?:{CURRENCY}[ \t]*)?(?P<value>\d[\d .,]*\d|\d)"

# Label on its own line, amount at the start of the next line.
NEXT_LINE_AMOUNT = rf"[ \t]*:?[ \t]*$\n[ \t]*{AMOUNT}"

# Optional tax rate between a tax label and its amount: "TVA (20%)",
# "TVA à 20%".
TAX_RATE = r"(?:[ \t]*\(?[ \t]*(?:à[ \t]*)?\d+(?:[.,]\d+)?[ \t]*%[ \t]*\)?)?"

# A value directly followed by "%" is a rate, not an amount.
NOT_A_RATE = r"(?!\d|[.,]\d|[ \t]*%)"

SUBTOTAL_LABELS = r"""
    (?:
        Sous[ \t\-]*total
        |
        subtotal
        |
        Total[ \t]+H\.?T\.?
        |
        Montant[ \t]+H\.?T\.?
    )
    (?!\w)
"""

TAX_LABELS = r"""
    (?:
        Total[ \t]+(?:T\.?V\.?A\.?|VAT)
        |
        Montant[ \t]+T\.?V\.?A\.?
        |
        T\.?V\.?A\.?
        |
        VAT
        |
        Tax[ \t]*Amount
        |
        Tax
    )
    (?!\w)
"""

SUBTOTAL_PATTERN = re.compile(
    rf"""
    ^[ \t]*
    {SUBTOTAL_LABELS}
    {CURRENCY_NOTE}
    [ \t]*[:\-]?[ \t]*
    {AMOUNT}
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

SUBTOTAL_NEXT_LINE_PATTERN = re.compile(
    rf"""
    ^[ \t]*
    {SUBTOTAL_LABELS}
    {CURRENCY_NOTE}
    {NEXT_LINE_AMOUNT}
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

TAX_AMOUNT_PATTERN = re.compile(
    rf"""
    (?:^|[ \t]{{2,}})
    {TAX_LABELS}
    {TAX_RATE}
    {CURRENCY_NOTE}
    [ \t]*[:\-]?[ \t]*
    {AMOUNT}
    {NOT_A_RATE}
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

TAX_AMOUNT_NEXT_LINE_PATTERN = re.compile(
    rf"""
    ^[ \t]*
    {TAX_LABELS}
    {TAX_RATE}
    {CURRENCY_NOTE}
    {NEXT_LINE_AMOUNT}
    {NOT_A_RATE}
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)


def _total_patterns(labels: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """Next-line and same-line patterns for one tier of total labels."""
    next_line = re.compile(
        rf"""
        ^[ \t]*
        (?:{labels})(?!\w)
        {CURRENCY_NOTE}
        {NEXT_LINE_AMOUNT}
        """,
        re.IGNORECASE | re.VERBOSE | re.MULTILINE,
    )
    same_line = re.compile(
        rf"""
        (?:^|[ \t]{{2,}})
        (?:{labels})(?!\w)
        {CURRENCY_NOTE}
        [ \t]*:?[ \t]*
        {AMOUNT}
        """,
        re.IGNORECASE | re.VERBOSE | re.MULTILINE,
    )
    return next_line, same_line


# Tiers are searched in order: an explicitly tax-inclusive or grand total wins
# over a bare "Total", which may be a pre-tax or pre-discount figure. Amount
# payable labels come last because they can be a balance after a deposit.
TOTAL_LABEL_TIERS = [
    r"total[ \t]*t\.?t\.?c\.? | montant[ \t]*t\.?t\.?c\.? | grand[ \t]+total",
    r"total",
    r"total[ \t]+due | (?:net|total)[ \t]+[àa][ \t]+payer",
]

TOTAL_PATTERNS = [
    pattern for labels in TOTAL_LABEL_TIERS for pattern in _total_patterns(labels)
]


def _valid_grouping(number_part: str, sep: str) -> bool:
    """True if splitting on `sep` looks like real thousands grouping:
    first group 1-3 digits, every subsequent group exactly 3 digits."""
    groups = number_part.split(sep)
    if len(groups) < 2:
        return True
    if not (1 <= len(groups[0]) <= 3):
        return False
    return all(len(g) == 3 for g in groups[1:])


def normalize_amount(raw: str) -> Decimal | None:
    if raw is None:
        return None

    text = raw.strip().replace(" ", "")
    if not text:
        return None

    has_comma = "," in text
    has_dot = "." in text

    if has_comma and has_dot:
        if text.rfind(",") > text.rfind("."):
            decimal_sep, thousands_sep = ",", "."
        else:
            decimal_sep, thousands_sep = ".", ","

        integer_part = text.split(decimal_sep)[0]
        if not _valid_grouping(integer_part, thousands_sep):
            return None

        text = text.replace(thousands_sep, "")
        if decimal_sep == ",":
            text = text.replace(",", ".")

    elif has_comma:
        if text.count(",") > 1:
            if not _valid_grouping(text, ","):
                return None
            text = text.replace(",", "")
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


def extract_total_amount(text: str) -> Decimal | None:
    for pattern in TOTAL_PATTERNS:
        match = pattern.search(text)
        if match:
            return normalize_amount(match.group("value"))
    return None
