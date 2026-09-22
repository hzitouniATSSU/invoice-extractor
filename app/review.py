from decimal import Decimal

from app.models import (
    ExtractionResult,
    InvoiceData,
    ReviewIssue,
    ReviewResult,
)
from app.tax_ids import is_valid_ice


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

def validate_invoice_data(invoice: InvoiceData) -> list[str]:
   
    problems = []
    if invoice.customer_ICE is not None and not is_valid_ice(invoice.customer_ICE):
        problems.append("Customer ICE must contain 15 digits.")
 
    totals_ok = is_totals_consistent(invoice.subtotal, invoice.tax_amount, invoice.total_amount)
    if totals_ok is False:
        problems.append("Subtotal + tax amount does not equal total amount.")
 
    return problems

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
