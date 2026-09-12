from pydantic import BaseModel,field_validator
from datetime import date
from typing import Optional,Literal
from decimal import Decimal
from dataclasses import dataclass,field


SUPPORTED_CURRENCIES = {"MAD", "EUR", "USD", "CAD", "AUD", "GBP", "JPY"}

class InvoiceData(BaseModel):
    invoice_number: str
    invoice_date: date
    supplier_name: str
    supplier_tax_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_ICE:  Optional[str] = None
    subtotal:  Optional[Decimal] = None
    tax_amount:  Optional[Decimal] = None
    total_amount: Decimal
    currency: str

    @field_validator("invoice_number", "supplier_name")
    @classmethod
    def must_not_be_blank(cls, value: str, info) -> str:
            value = value.strip()
            if not value:
                raise ValueError(f"{info.field_name} must not be blank")
            return value

    @field_validator("currency")
    @classmethod
    def must_be_supported_currency(cls, value: str) -> str:
            normalized = value.strip().upper()
            if not normalized:
                raise ValueError("currency must not be blank")
            if normalized not in SUPPORTED_CURRENCIES:
                raise ValueError(
                    f"Unsupported currency: {value!r}. "
                    f"Supported: {', '.join(sorted(SUPPORTED_CURRENCIES))}"
                )
            return normalized

class ExtractedInvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    supplier_name: Optional[str] = None
    supplier_tax_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_ICE:  Optional[str] = None
    subtotal:  Optional[Decimal] = None
    tax_amount:  Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None


@dataclass
class ReviewIssue: 
    field: str
    code: str
    message: str 
    severity: Literal["error", "warning"] = "error"


@dataclass
class ReviewResult:
    data: ExtractedInvoiceData
    issues: list[ReviewIssue]

    @property
    def status(self) -> Literal["ready", "needs_review", "blocked"]:
        if any (issue.severity == "error" for issue in self.issues):
            return "blocked"
        if any(issue.severity == "warning" for issue in self.issues):
            return "needs_review"
        return "ready"


@dataclass(frozen=True)
class CurrencyResult:
    status: Literal["found", "missing", "conflicting"]
    value: str | None = None
    candidates: frozenset[str] = field(default_factory=frozenset)


    @classmethod
    def found(cls, value:str) -> "CurrencyResult":
        return cls(status="found", value=value)

    @classmethod
    def missing(cls) -> "CurrencyResult":
        return cls(status="missing")

    @classmethod
    def conflicting(cls, candidates: set[str]) -> "CurrencyResult":
        return cls(status="conflicting", candidates=frozenset(candidates))
    



@dataclass(frozen=True)
class TaxIdResult:
    status: Literal["found", "missing", "conflicting"]
    label: str | None = None
    value: str | None = None
    candidates: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def found(cls, label:str, value:str) -> "TaxIdResult":
        return cls(status="found", label=label, value=value)

    @classmethod
    def missing(cls) -> "TaxIdResult":
        return cls(status="missing")

    @classmethod
    def conflicting(cls,label: str, candidates: set[str]) -> "TaxIdResult":
        return cls(status="conflicting", label=label,candidates=frozenset(candidates))


@dataclass
class ExtractionResult:
    data: ExtractedInvoiceData
    currency_result: CurrencyResult
    supplier_tax_id_result: TaxIdResult
    customer_ice_result: TaxIdResult