from decimal import Decimal, InvalidOperation
import re



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
    match = TOTAL_NEXT_LINE_PATTERN.search(text)
    if not match:
        match = TOTAL_PATTERN.search(text)
    if not match:
        return None
    return normalize_amount(match.group("value"))


