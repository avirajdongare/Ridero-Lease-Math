from decimal import Decimal

import pytest

from app.services.lease_math import (
    SUPPORTED_TERMS,
    ReverseQuoteResult,
    calculate_implied_money_factor,
    calculate_monthly_payment,
    calculate_reverse_quote,
    calculate_reverse_quote_fixed_residual,
    calculate_reverse_quote_percent_residual,
)

D = Decimal

# Baseline inputs; individual tests override what they exercise.
COMMON = {
    "target_monthly_payment": D("500"),
    "term_months": 36,
    "cash_down": D("0"),
    "money_factor": D("0.0025"),
    "fees": D("0"),
    "tax_rate": D("0"),
}
FIXED_BASE = {**COMMON, "residual_value": D("20000")}
PERCENT_BASE = {**COMMON, "residual_percent": D("0.60")}


def fixed_quote(**overrides) -> ReverseQuoteResult:
    return calculate_reverse_quote_fixed_residual(**{**FIXED_BASE, **overrides})


def percent_quote(**overrides) -> ReverseQuoteResult:
    return calculate_reverse_quote_percent_residual(**{**PERCENT_BASE, **overrides})


def forward_payment(result: ReverseQuoteResult, inputs: dict) -> Decimal:
    """Re-price the quoted (rounded) vehicle price and residual."""
    return calculate_monthly_payment(
        vehicle_price=result.vehicle_price,
        residual_value=result.residual_value,
        term_months=inputs["term_months"],
        cash_down=inputs["cash_down"],
        money_factor=inputs["money_factor"],
        fees=inputs["fees"],
        tax_rate=inputs["tax_rate"],
    )


# Expected values below were computed independently with exact rational
# arithmetic (fractions.Fraction), not with lease_math itself.


# --- Fixed residual (primary mode) -------------------------------------------


def test_fixed_residual_calculation() -> None:
    result = fixed_quote()
    assert result == ReverseQuoteResult(
        vehicle_price=D("33211.01"),
        residual_value=D("20000.00"),
        adjusted_cap_cost=D("33211.01"),
        total_depreciation=D("13211.01"),
        monthly_depreciation=D("366.97"),
        monthly_finance_charge=D("133.03"),
        pre_tax_payment=D("500.00"),
        monthly_tax=D("0.00"),
        monthly_payment=D("500.00"),
    )


def test_fixed_residual_24_month_case() -> None:
    result = fixed_quote(target_monthly_payment=D("450"), term_months=24, residual_value=D("18500"), money_factor=D("0.0021"))
    assert result.vehicle_price == D("27006.47")
    assert result.monthly_depreciation == D("354.44")
    assert result.monthly_finance_charge == D("95.56")
    assert result.monthly_payment == D("450.00")


def test_fixed_residual_60_month_case() -> None:
    result = fixed_quote(target_monthly_payment=D("725"), term_months=60, residual_value=D("19000"), money_factor=D("0.0028"))
    assert result.vehicle_price == D("50777.40")
    assert result.monthly_depreciation == D("529.62")
    assert result.monthly_finance_charge == D("195.38")
    assert result.monthly_payment == D("725.00")


def test_fixed_residual_zero_money_factor() -> None:
    # With MF = 0: P = n·T + R − C = 36·300 + 15000 − 0
    result = fixed_quote(target_monthly_payment=D("300"), residual_value=D("15000"), money_factor=D("0"))
    assert result.vehicle_price == D("25800.00")
    assert result.monthly_finance_charge == D("0.00")
    assert result.monthly_depreciation == D("300.00")


def test_fixed_residual_cash_down_adds_dollar_for_dollar() -> None:
    # Residual doesn't move with price, so $3000 down supports exactly $3000 more.
    result = fixed_quote(target_monthly_payment=D("300"), residual_value=D("15000"), money_factor=D("0"), cash_down=D("3000"))
    assert result.vehicle_price == D("28800.00")
    assert result.adjusted_cap_cost == D("25800.00")
    assert result.monthly_payment == D("300.00")


def test_fixed_residual_fees() -> None:
    result = fixed_quote(target_monthly_payment=D("300"), residual_value=D("15000"), money_factor=D("0"), fees=D("1000"))
    assert result.vehicle_price == D("24800.00")
    assert result.adjusted_cap_cost == D("25800.00")
    assert result.monthly_payment == D("300.00")


def test_fixed_residual_tax() -> None:
    # $540 at 8% tax == $500 pre-tax, so the price matches the untaxed case.
    result = fixed_quote(target_monthly_payment=D("540"), tax_rate=D("0.08"))
    assert result.vehicle_price == D("33211.01")
    assert result.pre_tax_payment == D("500.00")
    assert result.monthly_tax == D("40.00")
    assert result.monthly_payment == D("540.00")


def test_fixed_residual_all_inputs_combined() -> None:
    result = fixed_quote(
        target_monthly_payment=D("699"),
        cash_down=D("2500"),
        residual_value=D("28000"),
        money_factor=D("0.00215"),
        fees=D("1095"),
        tax_rate=D("0.0725"),
    )
    assert result == ReverseQuoteResult(
        vehicle_price=D("47159.35"),
        residual_value=D("28000.00"),
        adjusted_cap_cost=D("45754.35"),
        total_depreciation=D("17754.35"),
        monthly_depreciation=D("493.18"),
        monthly_finance_charge=D("158.57"),
        pre_tax_payment=D("651.75"),
        monthly_tax=D("47.25"),
        monthly_payment=D("699.00"),
    )


# --- Public example: Ridero Maserati ------------------------------------------
#
# Based only on publicly advertised numbers for a 2023 Maserati Grecale GT:
# $33,000 vehicle price, $20,500 residual, 36 months, $399/month.
#
# Ridero's money factor, fees, tax treatment and cash due at signing are NOT
# public. This fixture assumes $0 down, $0 fees and 0% tax, and back-solves
# the money factor those assumptions imply. That inferred money factor is NOT
# claimed to be Ridero's actual rate, and this test does NOT claim to
# reproduce Ridero's proprietary quote. Real leases may include taxes,
# acquisition fees, dealer fees, incentives, cap-cost reductions, and
# lender-specific rules that would change the implied rate.

MASERATI_PUBLIC = {
    "vehicle_price": D("33000"),
    "residual_value": D("20500"),
    "term_months": 36,
    "target_monthly_payment": D("399"),
    # Simplified assumptions (unknown in the real quote):
    "cash_down": D("0"),
    "fees": D("0"),
    "tax_rate": D("0"),
}


def test_public_maserati_example_under_simplified_assumptions() -> None:
    implied_mf = calculate_implied_money_factor(**MASERATI_PUBLIC)

    # Hand derivation: MF = [399 − (33000 − 20500)/36] / (33000 + 20500)
    #                     = (14364 − 12500) / (36 · 53500) = 233 / 240750
    #                     ≈ 0.000967809  (≈ 2.32% APR equivalent, × 2400)
    assert abs(implied_mf - D(233) / D(240750)) < D("1e-20")
    assert implied_mf.quantize(D("0.000000001")) == D("0.000967809")

    result = calculate_reverse_quote_fixed_residual(
        target_monthly_payment=MASERATI_PUBLIC["target_monthly_payment"],
        term_months=MASERATI_PUBLIC["term_months"],
        cash_down=MASERATI_PUBLIC["cash_down"],
        residual_value=MASERATI_PUBLIC["residual_value"],
        money_factor=implied_mf,
        fees=MASERATI_PUBLIC["fees"],
        tax_rate=MASERATI_PUBLIC["tax_rate"],
    )
    assert result == ReverseQuoteResult(
        vehicle_price=D("33000.00"),
        residual_value=D("20500.00"),
        adjusted_cap_cost=D("33000.00"),
        total_depreciation=D("12500.00"),
        monthly_depreciation=D("347.22"),
        monthly_finance_charge=D("51.78"),
        pre_tax_payment=D("399.00"),
        monthly_tax=D("0.00"),
        monthly_payment=D("399.00"),
    )


def test_implied_money_factor_round_trips_with_fees_down_and_tax() -> None:
    inputs = {**MASERATI_PUBLIC, "cash_down": D("2000"), "fees": D("1095"), "tax_rate": D("0.0725"), "target_monthly_payment": D("449")}
    implied_mf = calculate_implied_money_factor(**inputs)
    result = calculate_reverse_quote_fixed_residual(
        target_monthly_payment=inputs["target_monthly_payment"],
        term_months=inputs["term_months"],
        cash_down=inputs["cash_down"],
        residual_value=inputs["residual_value"],
        money_factor=implied_mf,
        fees=inputs["fees"],
        tax_rate=inputs["tax_rate"],
    )
    assert result.vehicle_price == D("33000.00")
    assert result.monthly_payment == D("449.00")


def test_implied_money_factor_rejects_payment_below_depreciation() -> None:
    # $300 < $347.22 of pure depreciation → would need a negative money factor.
    with pytest.raises(ValueError, match="negative"):
        calculate_implied_money_factor(**{**MASERATI_PUBLIC, "target_monthly_payment": D("300")})


# --- Percentage residual (simplified convenience mode) -----------------------


def test_percent_residual_hand_computed_fixture() -> None:
    # P = 400 / [(1 − 0.6)/36 + 0.0025·1.6] = 400 / 0.0151111… = 26470.588…
    result = percent_quote(target_monthly_payment=D("400"))
    assert result.vehicle_price == D("26470.59")
    assert result.residual_value == D("15882.35")
    assert result.monthly_depreciation == D("294.12")
    assert result.monthly_finance_charge == D("105.88")
    assert result.monthly_payment == D("400.00")


def test_percent_residual_calculation() -> None:
    result = percent_quote()
    assert result == ReverseQuoteResult(
        vehicle_price=D("33088.24"),
        residual_value=D("19852.94"),
        adjusted_cap_cost=D("33088.24"),
        # 13235.294… at full precision; 33088.24 − 19852.94 would give .30.
        total_depreciation=D("13235.29"),
        monthly_depreciation=D("367.65"),
        monthly_finance_charge=D("132.35"),
        pre_tax_payment=D("500.00"),
        monthly_tax=D("0.00"),
        monthly_payment=D("500.00"),
    )


def test_percent_residual_24_month_case() -> None:
    result = percent_quote(target_monthly_payment=D("400"), term_months=24, residual_percent=D("0.65"), money_factor=D("0.0020"))
    assert result.vehicle_price == D("22367.19")
    # 14538.675… from the full-precision price (not 0.65 × the rounded price).
    assert result.residual_value == D("14538.68")
    assert result.monthly_depreciation == D("326.19")
    assert result.monthly_finance_charge == D("73.81")
    assert result.monthly_payment == D("400.00")


def test_percent_residual_48_month_case() -> None:
    result = percent_quote(target_monthly_payment=D("650"), term_months=48, residual_percent=D("0.50"), money_factor=D("0.0030"))
    assert result.vehicle_price == D("43575.42")
    assert result.residual_value == D("21787.71")
    assert result.monthly_depreciation == D("453.91")
    assert result.monthly_finance_charge == D("196.09")
    assert result.monthly_payment == D("650.00")


def test_percent_residual_zero_money_factor() -> None:
    # With MF = 0: P = n·T / (1 − r) = 36·300 / 0.5
    result = percent_quote(target_monthly_payment=D("300"), residual_percent=D("0.50"), money_factor=D("0"))
    assert result.vehicle_price == D("21600.00")
    assert result.monthly_finance_charge == D("0.00")
    assert result.monthly_depreciation == D("300.00")


def test_percent_residual_cash_down() -> None:
    # Residual tracks price here, so each dollar down supports 1 / (1 − r)
    # dollars of price: 21600 + 3000 / 0.5 = 27600.
    result = percent_quote(target_monthly_payment=D("300"), residual_percent=D("0.50"), money_factor=D("0"), cash_down=D("3000"))
    assert result.vehicle_price == D("27600.00")
    assert result.adjusted_cap_cost == D("24600.00")
    assert result.monthly_payment == D("300.00")


def test_percent_residual_fees() -> None:
    result = percent_quote(target_monthly_payment=D("300"), residual_percent=D("0.50"), money_factor=D("0"), fees=D("1000"))
    assert result.vehicle_price == D("19600.00")
    assert result.adjusted_cap_cost == D("20600.00")
    assert result.monthly_payment == D("300.00")


def test_percent_residual_tax() -> None:
    result = percent_quote(target_monthly_payment=D("540"), tax_rate=D("0.08"))
    assert result.vehicle_price == D("33088.24")
    assert result.pre_tax_payment == D("500.00")
    assert result.monthly_tax == D("40.00")
    assert result.monthly_payment == D("540.00")


def test_percent_residual_all_inputs_combined() -> None:
    result = percent_quote(
        target_monthly_payment=D("699"),
        cash_down=D("2500"),
        residual_percent=D("0.58"),
        money_factor=D("0.00215"),
        fees=D("1095"),
        tax_rate=D("0.0725"),
    )
    assert result == ReverseQuoteResult(
        vehicle_price=D("46057.63"),
        residual_value=D("26713.43"),
        adjusted_cap_cost=D("44652.63"),
        total_depreciation=D("17939.20"),
        monthly_depreciation=D("498.31"),
        monthly_finance_charge=D("153.44"),
        pre_tax_payment=D("651.75"),
        monthly_tax=D("47.25"),
        monthly_payment=D("699.00"),
    )


# --- Dispatcher --------------------------------------------------------------


def test_dispatcher_routes_to_each_mode() -> None:
    assert calculate_reverse_quote(**COMMON, residual_value=D("20000")) == fixed_quote()
    assert calculate_reverse_quote(**COMMON, residual_percent=D("0.60")) == percent_quote()


@pytest.mark.parametrize(
    "residuals",
    [{}, {"residual_value": D("20000"), "residual_percent": D("0.60")}],
)
def test_dispatcher_requires_exactly_one_residual(residuals: dict) -> None:
    with pytest.raises(ValueError):
        calculate_reverse_quote(**COMMON, **residuals)


# --- Precision, rounding, determinism ----------------------------------------


def test_deterministic_repeated_calculations() -> None:
    kwargs = {"tax_rate": D("0.0725"), "fees": D("995"), "cash_down": D("1500")}
    first_fixed, first_percent = fixed_quote(**kwargs), percent_quote(**kwargs)
    for _ in range(100):
        assert fixed_quote(**kwargs) == first_fixed
        assert percent_quote(**kwargs) == first_percent


def test_accepts_int_and_string_inputs() -> None:
    assert percent_quote(target_monthly_payment=500, residual_percent="0.60") == percent_quote()
    assert fixed_quote(target_monthly_payment="500", residual_value=20000) == fixed_quote()


@pytest.mark.parametrize("quote", [fixed_quote, percent_quote])
def test_returns_decimals_rounded_to_cents(quote) -> None:
    result = quote(tax_rate=D("0.0725"), money_factor=D("0.00187"))
    for value in vars(result).values():
        assert isinstance(value, Decimal)
        assert value.as_tuple().exponent == -2


ROUND_TRIP_CASES = [
    {},
    {"target_monthly_payment": D("249.99"), "money_factor": D("0.00042")},
    {"target_monthly_payment": D("1234.56"), "cash_down": D("5000"), "fees": D("1295.50"), "tax_rate": D("0.095")},
    {"target_monthly_payment": D("399"), "money_factor": D("0"), "tax_rate": D("0.06625")},
    {"target_monthly_payment": D("875.33"), "money_factor": D("0.0041"), "fees": D("750")},
]


@pytest.mark.parametrize("term", sorted(SUPPORTED_TERMS))
@pytest.mark.parametrize("overrides", ROUND_TRIP_CASES)
@pytest.mark.parametrize(
    "base, quote",
    [
        ({**FIXED_BASE, "residual_value": D("15000")}, calculate_reverse_quote_fixed_residual),
        ({**PERCENT_BASE, "residual_percent": D("0.55")}, calculate_reverse_quote_percent_residual),
    ],
    ids=["fixed", "percent"],
)
def test_reverse_then_forward_reproduces_target(base: dict, quote, overrides: dict, term: int) -> None:
    inputs = {**base, **overrides, "term_months": term}
    result = quote(**inputs)
    target = inputs["target_monthly_payment"]

    assert abs(forward_payment(result, inputs) - target) <= D("0.01")
    assert abs(result.monthly_payment - target) <= D("0.01")


# --- Validation --------------------------------------------------------------


def test_float_inputs_are_rejected() -> None:
    with pytest.raises(TypeError):
        percent_quote(target_monthly_payment=500.0)
    with pytest.raises(TypeError):
        fixed_quote(money_factor=0.0025)
    with pytest.raises(TypeError):
        fixed_quote(residual_value=20000.0)


SHARED_INVALID = [
    {"target_monthly_payment": D("-500")},
    {"target_monthly_payment": D("0")},
    {"money_factor": D("-0.0001")},
    {"tax_rate": D("-0.01")},
    {"tax_rate": D("1")},
    {"fees": D("-1")},
    {"cash_down": D("-1")},
    {"target_monthly_payment": "abc"},
    {"target_monthly_payment": D("NaN")},
]


@pytest.mark.parametrize(
    "overrides",
    SHARED_INVALID
    + [
        {"residual_percent": D("0")},
        {"residual_percent": D("1")},
        {"residual_percent": D("58")},
        {"residual_percent": D("-0.5")},
    ],
)
def test_percent_invalid_values_raise(overrides: dict) -> None:
    with pytest.raises(ValueError):
        percent_quote(**overrides)


@pytest.mark.parametrize(
    "overrides",
    SHARED_INVALID + [{"residual_value": D("0")}, {"residual_value": D("-15000")}],
)
def test_fixed_invalid_values_raise(overrides: dict) -> None:
    with pytest.raises(ValueError):
        fixed_quote(**overrides)


@pytest.mark.parametrize("term", [0, -36, 12, 27, 37, 39, 72])
@pytest.mark.parametrize("quote", [fixed_quote, percent_quote])
def test_unsupported_terms_raise(quote, term: int) -> None:
    with pytest.raises(ValueError):
        quote(term_months=term)


def test_supported_terms_are_exactly_24_36_48_60() -> None:
    assert SUPPORTED_TERMS == {24, 36, 48, 60}


def test_non_int_term_raises() -> None:
    with pytest.raises(TypeError):
        percent_quote(term_months=D("36"))


def test_fixed_residual_non_positive_vehicle_price_raises() -> None:
    # Huge fees eat the whole payment: numerator goes negative.
    with pytest.raises(ValueError, match="positive vehicle price"):
        fixed_quote(target_monthly_payment=D("100"), residual_value=D("1000"), fees=D("50000"))


def test_fixed_residual_cap_cost_below_residual_raises() -> None:
    # Tiny payment with a large residual: the price solves below the residual.
    with pytest.raises(ValueError, match="below the residual"):
        fixed_quote(target_monthly_payment=D("50"), residual_value=D("40000"), money_factor=D("0.004"))


def test_fixed_residual_non_positive_cap_cost_raises() -> None:
    # Cap cost = [T + R·(1/n − MF)] / (1/n + MF), so it can only go <= 0 when
    # MF > 1/n (here 0.05 > 1/24). Cash down keeps the solved price positive.
    with pytest.raises(ValueError, match="adjusted cap cost must be > 0"):
        fixed_quote(
            target_monthly_payment=D("100"),
            term_months=24,
            residual_value=D("20000"),
            money_factor=D("0.05"),
            cash_down=D("10000"),
        )


def test_percent_residual_cash_down_too_large_raises() -> None:
    with pytest.raises(ValueError, match="below the residual"):
        percent_quote(target_monthly_payment=D("50"), cash_down=D("50000"))
