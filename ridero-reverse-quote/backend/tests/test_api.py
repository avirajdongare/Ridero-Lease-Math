from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.lease_math import calculate_implied_money_factor

client = TestClient(app)

FIXED_REQUEST = {
    "target_monthly_payment": "500.00",
    "term_months": 36,
    "cash_down": "0.00",
    "money_factor": "0.0025",
    "fees": "0.00",
    "tax_rate": "0.00",
    "residual_value": "20000.00",
    "residual_percent": None,
}

PERCENT_REQUEST = {
    **FIXED_REQUEST,
    "residual_value": None,
    "residual_percent": "0.60",
}

MONEY_FIELDS = [
    "vehicle_price",
    "residual_value",
    "adjusted_cap_cost",
    "total_depreciation",
    "monthly_depreciation",
    "monthly_finance_charge",
    "pre_tax_payment",
    "monthly_tax",
    "monthly_payment",
]


def post_quote(body: dict):
    return client.post("/quote/reverse", json=body)


def assert_422(response, fragment: str) -> None:
    assert response.status_code == 422
    messages = " ".join(error["msg"] for error in response.json()["detail"])
    assert fragment in messages


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_fixed_residual_request() -> None:
    response = post_quote(FIXED_REQUEST)
    assert response.status_code == 200
    assert response.json() == {
        "mode": "fixed_residual",
        "vehicle_price": "33211.01",
        "residual_value": "20000.00",
        "adjusted_cap_cost": "33211.01",
        "total_depreciation": "13211.01",
        "monthly_depreciation": "366.97",
        "monthly_finance_charge": "133.03",
        "pre_tax_payment": "500.00",
        "monthly_tax": "0.00",
        "monthly_payment": "500.00",
    }


def test_percent_residual_request() -> None:
    response = post_quote(PERCENT_REQUEST)
    assert response.status_code == 200
    assert response.json() == {
        "mode": "percent_residual",
        "vehicle_price": "33088.24",
        "residual_value": "19852.94",
        "adjusted_cap_cost": "33088.24",
        "total_depreciation": "13235.29",
        "monthly_depreciation": "367.65",
        "monthly_finance_charge": "132.35",
        "pre_tax_payment": "500.00",
        "monthly_tax": "0.00",
        "monthly_payment": "500.00",
    }


def test_residual_percent_can_be_omitted_instead_of_null() -> None:
    body = {k: v for k, v in FIXED_REQUEST.items() if k != "residual_percent"}
    assert post_quote(body).json()["mode"] == "fixed_residual"


def test_maserati_public_fixture_request() -> None:
    # Public numbers only; money factor is inferred under $0 down / $0 fees /
    # 0% tax and is NOT claimed to be Ridero's actual rate. See
    # test_public_maserati_example_under_simplified_assumptions.
    implied_mf = calculate_implied_money_factor(
        vehicle_price=Decimal("33000"),
        residual_value=Decimal("20500"),
        term_months=36,
        target_monthly_payment=Decimal("399"),
        cash_down=Decimal("0"),
        fees=Decimal("0"),
        tax_rate=Decimal("0"),
    )
    response = post_quote(
        {
            "target_monthly_payment": "399.00",
            "term_months": 36,
            "cash_down": "0.00",
            "money_factor": str(implied_mf),
            "fees": "0.00",
            "tax_rate": "0.00",
            "residual_value": "20500.00",
            "residual_percent": None,
        }
    )
    assert response.status_code == 200
    assert response.json() == {
        "mode": "fixed_residual",
        "vehicle_price": "33000.00",
        "residual_value": "20500.00",
        "adjusted_cap_cost": "33000.00",
        "total_depreciation": "12500.00",
        "monthly_depreciation": "347.22",
        "monthly_finance_charge": "51.78",
        "pre_tax_payment": "399.00",
        "monthly_tax": "0.00",
        "monthly_payment": "399.00",
    }


def test_maserati_with_rounded_money_factor_from_contract_example() -> None:
    # The documented example sends MF rounded to 11 places; still lands on $33,000.
    body = {**FIXED_REQUEST, "target_monthly_payment": "399.00", "money_factor": "0.00096780893", "residual_value": "20500.00"}
    data = post_quote(body).json()
    assert data["vehicle_price"] == "33000.00"
    assert data["monthly_payment"] == "399.00"


def test_both_residual_types_rejected() -> None:
    response = post_quote({**FIXED_REQUEST, "residual_percent": "0.60"})
    assert_422(response, "exactly one of residual_value or residual_percent")


def test_neither_residual_type_rejected() -> None:
    response = post_quote({**FIXED_REQUEST, "residual_value": None})
    assert_422(response, "exactly one of residual_value or residual_percent")


def test_negative_money_factor_rejected() -> None:
    response = post_quote({**FIXED_REQUEST, "money_factor": "-0.0001"})
    assert_422(response, "money_factor must be >= 0")
    assert response.json()["detail"][0]["type"] == "lease_validation_error"


@pytest.mark.parametrize("term", [12, 39, 72])
def test_invalid_term_rejected(term: int) -> None:
    response = post_quote({**FIXED_REQUEST, "term_months": term})
    assert_422(response, "term_months must be one of [24, 36, 48, 60]")


def test_non_integer_term_rejected() -> None:
    assert post_quote({**FIXED_REQUEST, "term_months": "36"}).status_code == 422
    assert post_quote({**FIXED_REQUEST, "term_months": 36.0}).status_code == 422


def test_impossible_quote_rejected() -> None:
    # $50/month can't carry a $40,000 residual: price solves below the residual.
    response = post_quote({**FIXED_REQUEST, "target_monthly_payment": "50.00", "residual_value": "40000.00", "money_factor": "0.004"})
    assert_422(response, "below the residual")


@pytest.mark.parametrize(
    "field, value, fragment",
    [
        ("target_monthly_payment", "-399.00", "target_monthly_payment must be > 0"),
        ("residual_percent", "1.5", "residual_percent must be a fraction"),
        ("fees", "-1.00", "fees must be >= 0"),
        ("tax_rate", "-0.01", "tax_rate must be"),
    ],
)
def test_domain_validation_surfaces_as_422(field: str, value: str, fragment: str) -> None:
    body = PERCENT_REQUEST if field == "residual_percent" else FIXED_REQUEST
    assert_422(post_quote({**body, field: value}), fragment)


@pytest.mark.parametrize("field", ["target_monthly_payment", "money_factor", "residual_value", "fees"])
def test_json_float_numbers_rejected(field: str) -> None:
    response = post_quote({**FIXED_REQUEST, field: 0.1 if field != "target_monthly_payment" else 399.99})
    assert_422(response, "decimal strings")


@pytest.mark.parametrize("value", ["abc", "NaN", "Infinity", ""])
def test_non_numeric_strings_rejected(value: str) -> None:
    assert post_quote({**FIXED_REQUEST, "target_monthly_payment": value}).status_code == 422


def test_whole_number_json_ints_accepted() -> None:
    response = post_quote({**FIXED_REQUEST, "target_monthly_payment": 500, "residual_value": 20000, "fees": 0})
    assert response.status_code == 200
    assert response.json()["vehicle_price"] == "33211.01"


def test_missing_required_field_rejected() -> None:
    body = {k: v for k, v in FIXED_REQUEST.items() if k != "money_factor"}
    assert post_quote(body).status_code == 422


def test_unknown_field_rejected() -> None:
    assert post_quote({**FIXED_REQUEST, "msrp": "50000"}).status_code == 422


@pytest.mark.parametrize("body", [FIXED_REQUEST, PERCENT_REQUEST])
def test_financial_values_serialized_as_strings(body: dict) -> None:
    response = post_quote(body)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"mode", *MONEY_FIELDS}
    for field in MONEY_FIELDS:
        value = data[field]
        assert isinstance(value, str), f"{field} should be a string, got {type(value).__name__}"
        # Exactly two decimal places, parseable as Decimal.
        assert Decimal(value).as_tuple().exponent == -2
    # Raw body uses quoted strings, not JSON numbers.
    assert '"vehicle_price":"' in response.text


def test_cors_allows_configured_origin() -> None:
    response = client.options(
        "/quote/reverse",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin() -> None:
    response = client.options(
        "/quote/reverse",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers
