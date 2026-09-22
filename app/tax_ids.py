import re

from app.models import TaxIdResult

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


def is_ice_label(label: str) -> bool:
    return label.strip().upper() == "ICE"


def is_valid_ice(value: str) -> bool:
    """ICE numbers are 15 digits. Strips formatting characters we
    explicitly allow (currently just spaces, per the "001 234 567 000 089"
    grouping style) before checking length/digit-only."""
    cleaned = value.replace(" ", "")
    return bool(re.fullmatch(r"\d{15}", cleaned))


SUPPLIER_TAX_ID_PRIORITY = ["ICE", "IF", "IDENTIFIANT FISCAL", "TAX ID"]


def _distinct_values_for_label(
    entries: list[tuple[str, str]], wanted_label: str
) -> set[str]:
    return {value for label, value in entries if label == wanted_label}


def extract_customer_ice_from_context(text: str) -> TaxIdResult:
    matches = CUSTOMER_ICE_CONTEXT_PATTERN.finditer(text)

    values = {match.group("value").strip() for match in matches}

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
        match.group("value").strip() for match in GENERIC_ICE_PATTERN.finditer(section)
    }

    if len(values) == 1:
        return TaxIdResult.found("ICE", values.pop())

    if len(values) > 1:
        return TaxIdResult.conflicting("ICE", values)

    return TaxIdResult.missing()


def select_supplier_tax_id_result(entries: list[tuple[str, str]]) -> TaxIdResult:
    for wanted_label in SUPPLIER_TAX_ID_PRIORITY:
        values = _distinct_values_for_label(entries, wanted_label)
        if len(values) == 1:
            return TaxIdResult.found(wanted_label, values.pop())
        if len(values) > 1:
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


def select_customer_ice_result(
    entries: list[tuple[str, str]],
) -> TaxIdResult:
    values = _distinct_values_for_label(entries, "ICE")
    if len(values) == 1:
        return TaxIdResult.found("ICE", values.pop())
    if len(values) > 1:
        return TaxIdResult.conflicting("ICE", values)
    return TaxIdResult.missing()
