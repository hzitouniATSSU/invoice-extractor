"""End-to-end robustness corpus: invoice text -> extraction -> review.

Every business, person and identifier below is invented. Each case lists
only the fields it is meant to pin down, plus the expected review status.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.pipeline import extract_invoice
from app.review import review_invoice

CORPUS = [
    pytest.param(
        """FACTURE N° FA-2026-0142
Date : 14/09/2026
Fournisseur : Menara Bureautique SARL
Fournisseur ICE : 002814593000071
Client : Riad Tadla Services
Client ICE : 001957302000048
Total HT : 1 234,56 DH
TVA 20% : 246,91 DH
Total TTC : 1 481,47 DH
""",
        dict(
            invoice_number="FA-2026-0142",
            invoice_date=date(2026, 9, 14),
            supplier_name="Menara Bureautique SARL",
            supplier_tax_id="002814593000071",
            customer_name="Riad Tadla Services",
            customer_ICE="001957302000048",
            subtotal=Decimal("1234.56"),
            tax_amount=Decimal("246.91"),
            total_amount=Decimal("1481.47"),
            currency="MAD",
        ),
        "ready",
        id="fr-space-grouping-dh",
    ),
    pytest.param(
        """Facture N° 2026/77
Date facture : 02.03.2026
Fournisseur : Atlas Froid SARL
Total HT : 10.000,00 MAD
TVA (20%) : 2.000,00 MAD
Total TTC : 12.000,00 MAD
""",
        dict(
            invoice_date=date(2026, 3, 2),
            subtotal=Decimal("10000.00"),
            tax_amount=Decimal("2000.00"),
            total_amount=Decimal("12000.00"),
        ),
        "ready",
        id="fr-dot-grouping-mad",
    ),
    pytest.param(
        """Invoice #: INV-5521
Invoice Date: 2026-01-15
Due Date: 2026-02-14
Supplier Name: Harbor Lane Consulting LLC
Customer Name: Oasis Retail Group
Subtotal: $1,234.56
Tax: $123.46
Total: $1,358.02
""",
        dict(
            invoice_number="INV-5521",
            invoice_date=date(2026, 1, 15),
            supplier_name="Harbor Lane Consulting LLC",
            customer_name="Oasis Retail Group",
            subtotal=Decimal("1234.56"),
            tax_amount=Decimal("123.46"),
            total_amount=Decimal("1358.02"),
            currency="USD",
        ),
        "ready",
        id="en-dollar-prefix-comma-grouping",
    ),
    pytest.param(
        """Order Date: 01/09/2026
N° de facture : FA-2026-31
Date de facture : 05/09/2026
Fournisseur : Cèdre Conseil
Total H.T : 500,00 €
T.V.A 20% : 100,00 €
Total T.T.C : 600,00 €
""",
        dict(
            invoice_number="FA-2026-31",
            invoice_date=date(2026, 9, 5),
            subtotal=Decimal("500.00"),
            tax_amount=Decimal("100.00"),
            total_amount=Decimal("600.00"),
            currency="EUR",
        ),
        "ready",
        id="fr-dotted-labels-eur-order-date-first",
    ),
    pytest.param(
        """INVOICE / FACTURE
Invoice No: MX-2026-5
Date de facture : 10/10/2026
Supplier: Kasbah Digital
Client : Marrakech Events
Subtotal: 2 000,00 MAD
TVA 20% : 400,00 MAD
Total TTC : 2 400,00 MAD
""",
        dict(
            invoice_number="MX-2026-5",
            customer_name="Marrakech Events",
            total_amount=Decimal("2400.00"),
        ),
        "ready",
        id="mixed-fr-en-labels",
    ),
    pytest.param(
        """   FACTURE   N°   :   FA-2026-9
   DATE   :   09/09/2026
   FOURNISSEUR   :   ORIENT PACK SARL
   TOTAL HT   :   800,00   DH
   TVA 20%   :   160,00   DH
   TOTAL TTC   :   960,00   DH
""",
        dict(
            invoice_number="FA-2026-9",
            supplier_name="ORIENT PACK SARL",
            subtotal=Decimal("800.00"),
            tax_amount=Decimal("160.00"),
            total_amount=Decimal("960.00"),
        ),
        "ready",
        id="uppercase-extra-whitespace",
    ),
    pytest.param(
        """Facture N° FA-30
Date : 09/09/2026
Fournisseur : Orient Pack
Total HT
800,00
TVA 20%
160,00
Total TTC
960,00
DH
""",
        dict(
            subtotal=Decimal("800.00"),
            tax_amount=Decimal("160.00"),
            total_amount=Decimal("960.00"),
        ),
        "ready",
        id="labels-above-values",
    ),
    pytest.param(
        """Facture N° 2026.0045
Date : 03/03/2026
Fournisseur : Sahara Lumière
Montant HT : 1 000,00 DH
TVA : 20 %
Montant TVA : 200,00 DH
Net à payer : 1 200,00 DH
Arrêtée la présente facture à la somme de : mille deux cents dirhams TTC
""",
        dict(
            invoice_number="2026.0045",
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("200.00"),
            total_amount=Decimal("1200.00"),
            currency="MAD",
        ),
        "ready",
        id="fr-montant-labels-rate-line-amount-in-words",
    ),
    pytest.param(
        """Votre réf : BC-2026-778
Facture N° FA-2026-0031
Date : 05/05/2026
Fournisseur : Dune Print
Fournisseur ICE : 002814593000071 - IF : 40123987
Client : Riad Tadla
Client ICE : 001957302000048   RC : 55123
Total : 1 000,00 Dhs
TVA 20% : 200,00 Dhs
Total TTC : 1 200,00 Dhs
""",
        dict(
            invoice_number="FA-2026-0031",
            supplier_tax_id="002814593000071",
            customer_ICE="001957302000048",
            total_amount=Decimal("1200.00"),
            currency="MAD",
        ),
        "ready",
        id="po-ref-first-identifiers-one-line-bare-total-first",
    ),
    pytest.param(
        """Invoice No: 42
Date: 05/05/2026
Supplier: Dune Print
Total: 1500 DHS
""",
        dict(
            invoice_number="42",
            customer_name=None,
            customer_ICE=None,
            subtotal=None,
            tax_amount=None,
            total_amount=Decimal("1500"),
        ),
        "ready",
        id="whole-number-total-optional-fields-absent",
    ),
    pytest.param(
        """Invoice No: INV-6
Invoice Date: 2026-03-03
Vendor ID: V-00912
Vendor: Palm Grove Ltd
Subtotal: 1,000.00 USD
VAT (10%): 100.00 USD
Grand Total: 1,100.00 USD
""",
        dict(
            supplier_name="Palm Grove Ltd",
            total_amount=Decimal("1100.00"),
        ),
        "ready",
        id="en-grand-total-vendor-id-line",
    ),
    pytest.param(
        """Facture N° FA-15
Date : 03/03/2026
Fournisseur : Sahara Lumière
Sous-total : 1 000,00 DH
Remise 10% : 100,00 DH
Total HT : 900,00 DH
TVA 20% : 180,00 DH
Total TTC : 1 080,00 DH
""",
        dict(
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("180.00"),
            total_amount=Decimal("1080.00"),
        ),
        "needs_review",
        id="discount-pre-discount-subtotal-flags-review",
    ),
    # Adversarial: wrong or missing data must stay visible, never guessed.
    pytest.param(
        """Invoice No: INV-4
Delivery Date: 2026-10-30
Supplier: Palm Grove Ltd
Total: 100 USD
""",
        dict(invoice_date=None),
        "blocked",
        id="only-a-delivery-date-blocks",
    ),
    pytest.param(
        """Facture N° 002814593000071
Date : 03/03/2026
Fournisseur : Sahara Lumière
CLIENT RIAD TADLA SARL
ICE : 0019573020000489
Total TTC : 100 DH
""",
        dict(
            invoice_number="002814593000071",
            supplier_tax_id=None,
            customer_ICE=None,
        ),
        "ready",
        id="invoice-number-and-long-number-are-not-ice",
    ),
    pytest.param(
        """Facture N° FA-32
Date : 09/09/2026
Fournisseur : Orient Pack
TVA 20% : 160,00 DH
Total TTC : 1.23.45 DH
""",
        dict(tax_amount=Decimal("160.00"), total_amount=None),
        "blocked",
        id="malformed-total-not-replaced-by-tax",
    ),
    pytest.param(
        """Invoice No: INV-40
Invoice Date: 2026-03-03
Supplier: Palm Grove Ltd
Total excl. VAT: 1,000.00 EUR
VAT 20%: 200.00 EUR
Total incl. VAT: 1,200.00 EUR
""",
        dict(subtotal=None, tax_amount=Decimal("200.00"), total_amount=None),
        "blocked",
        id="unsupported-total-label-blocks-instead-of-guessing",
    ),
    pytest.param(
        """Invoice No: INV-50
Invoice Date: 2026-03-03
Supplier: Palm Grove Ltd
Total TTC: 1,200.00 USD
Bank charges: 15.00 EUR
""",
        dict(currency=None),
        "blocked",
        id="conflicting-currencies-block",
    ),
]


@pytest.mark.parametrize("text, expected, expected_status", CORPUS)
def test_synthetic_invoice_corpus(text, expected, expected_status):
    extraction = extract_invoice(text)
    review = review_invoice(extraction)

    actual = extraction.data.model_dump()
    assert {field: actual[field] for field in expected} == expected
    assert review.status == expected_status
