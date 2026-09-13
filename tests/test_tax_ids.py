import pytest

from app.tax_ids import (
    is_ice_label,
    is_valid_ice,
    select_customer_ice_result,
    select_supplier_tax_id_result,
)



@pytest.mark.parametrize(
    "value, expected",
    [
        ("001234567000089", True),
        ("001 234 567 000 089", True),
        ("00123456700008", False),
        ("0012345670000899", False),
        ("00123456700008A", False),
        ("001-234-567-000-089", False),
        ("", False),
    ],
)
def test_is_valid_ice(value, expected):
    assert is_valid_ice(value) == expected

@pytest.mark.parametrize(
    "entries, expected_status, expected_value",
    [
        ([("ICE", "001234567000089")], "found", "001234567000089"),
        (
            [
                ("ICE", "001234567000089"),
                ("ICE", "001234567000089"),
            ],
            "found",
            "001234567000089",
        ),
        (
            [
                ("ICE", "001234567000089"),
                ("ICE", "999999999999999"),
            ],
            "conflicting",
            None,
        ),
        ([], "missing", None),
    ],
)
def test_select_customer_ice(entries, expected_status, expected_value):
    result = select_customer_ice_result(entries)

    assert result.status == expected_status
    assert result.value == expected_value


@pytest.mark.parametrize(
    "entries, expected_status, expected_value",
    [
        (
            [
                ("ICE", "001234567000000"),
                ("IF", "87654321"),
            ],
            "found",
            "001234567000000",
        ),
        (
            [
                ("ICE", "001234567000000"),
                ("ICE", "001234567000000"),
            ],
            "found",
            "001234567000000",
        ),
        (
            [
                ("ICE", "001234567000000"),
                ("ICE", "999999999999999"),
            ],
            "conflicting",
            None,
        ),
        ([("IF", "87654321")], "found", "87654321"),
        (
            [("IDENTIFIANT FISCAL", "33333333")],
            "found",
            "33333333",
        ),
        ([], "missing", None),
    ],
)
def test_select_supplier_tax_id(entries, expected_status, expected_value):
    result = select_supplier_tax_id_result(entries)

    assert result.status == expected_status
    assert result.value == expected_value