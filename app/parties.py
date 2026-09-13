import re

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

