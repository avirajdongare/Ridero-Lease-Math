"""Reverse lease quote math.

Given a target monthly lease payment, solve directly (closed form, no
iteration) for the maximum vehicle price that payment can support.

Two modes:

- **Fixed residual (primary).** The residual is a fixed dollar amount, as on a
  real lender rate sheet / quote. Use ``calculate_reverse_quote_fixed_residual``.
- **Percentage residual (simplified convenience model).** The residual is a
  percentage of the *solved* vehicle price, so it scales with the price being
  solved for. Real residuals are a percentage of MSRP, not of the negotiated
  price, so this mode is an approximation. Use
  ``calculate_reverse_quote_percent_residual``.

``calculate_reverse_quote`` dispatches to one of the two based on which
residual argument is given.

All money math uses ``Decimal``. Floats are rejected at the boundary so binary
rounding error can never leak in. Intermediate values (price, depreciation,
finance charge, tax) keep full precision; only the returned currency values
are rounded to cents with ``ROUND_HALF_UP``.

Conventions:
- ``residual_percent`` and ``tax_rate`` are fractions (0.58 means 58%).
- ``money_factor`` is the raw lease money factor (e.g. 0.00250).
- Tax is applied to the monthly payment (monthly-payment tax states).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

SUPPORTED_TERMS: frozenset[int] = frozenset({24, 36, 48, 60})

CENT = Decimal("0.01")
ONE = Decimal(1)

# Working precision for intermediate calculations, independent of whatever
# the caller's global decimal context happens to be.
_PRECISION = 34

Number = Decimal | int | str


@dataclass(frozen=True)
class ReverseQuoteResult:
    vehicle_price: Decimal
    residual_value: Decimal
    adjusted_cap_cost: Decimal
    total_depreciation: Decimal
    monthly_depreciation: Decimal
    monthly_finance_charge: Decimal
    pre_tax_payment: Decimal
    monthly_tax: Decimal
    monthly_payment: Decimal


@dataclass(frozen=True)
class _PaymentBreakdown:
    adjusted_cap_cost: Decimal
    monthly_depreciation: Decimal
    monthly_finance_charge: Decimal
    pre_tax_payment: Decimal
    monthly_tax: Decimal
    monthly_payment: Decimal


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _to_decimal(name: str, value: Number) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"{name} must be a Decimal, int, or numeric string, not {type(value).__name__}")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, str)):
        try:
            result = Decimal(value)
        except ArithmeticError as exc:
            raise ValueError(f"{name} is not a valid number: {value!r}") from exc
    else:
        raise TypeError(f"{name} must be a Decimal, int, or numeric string, not {type(value).__name__}")
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _validate_term(term_months: int) -> int:
    if isinstance(term_months, bool) or not isinstance(term_months, int):
        raise TypeError("term_months must be an int")
    if term_months not in SUPPORTED_TERMS:
        raise ValueError(f"term_months must be one of {sorted(SUPPORTED_TERMS)}, got {term_months}")
    return term_months


def _validate_common(
    term_months: int,
    cash_down: Number,
    money_factor: Number,
    fees: Number,
    tax_rate: Number,
) -> tuple[int, Decimal, Decimal, Decimal, Decimal]:
    n = _validate_term(term_months)
    d = _to_decimal("cash_down", cash_down)
    m = _to_decimal("money_factor", money_factor)
    f = _to_decimal("fees", fees)
    t = _to_decimal("tax_rate", tax_rate)

    if d < 0:
        raise ValueError("cash_down must be >= 0")
    if m < 0:
        raise ValueError("money_factor must be >= 0")
    if f < 0:
        raise ValueError("fees must be >= 0")
    if not (0 <= t < 1):
        raise ValueError("tax_rate must be a fraction in [0, 1) (e.g. 0.0825)")
    return n, d, m, f, t


def _validate_target(target_monthly_payment: Number) -> Decimal:
    target = _to_decimal("target_monthly_payment", target_monthly_payment)
    if target <= 0:
        raise ValueError("target_monthly_payment must be > 0")
    return target


def _validate_residual_percent(residual_percent: Number) -> Decimal:
    r = _to_decimal("residual_percent", residual_percent)
    if not (0 < r < 1):
        raise ValueError("residual_percent must be a fraction strictly between 0 and 1 (e.g. 0.58)")
    return r


def _validate_residual_value(residual_value: Number) -> Decimal:
    rv = _to_decimal("residual_value", residual_value)
    if rv <= 0:
        raise ValueError("residual_value must be > 0")
    return rv


def _payment_breakdown(
    vehicle_price: Decimal,
    residual_value: Decimal,
    n: int,
    d: Decimal,
    m: Decimal,
    f: Decimal,
    t: Decimal,
) -> _PaymentBreakdown:
    """Forward lease formula at full precision (no rounding)."""
    adjusted_cap_cost = vehicle_price + f - d
    monthly_depreciation = (adjusted_cap_cost - residual_value) / n
    monthly_finance_charge = (adjusted_cap_cost + residual_value) * m
    pre_tax_payment = monthly_depreciation + monthly_finance_charge
    monthly_tax = pre_tax_payment * t
    return _PaymentBreakdown(
        adjusted_cap_cost=adjusted_cap_cost,
        monthly_depreciation=monthly_depreciation,
        monthly_finance_charge=monthly_finance_charge,
        pre_tax_payment=pre_tax_payment,
        monthly_tax=monthly_tax,
        monthly_payment=pre_tax_payment + monthly_tax,
    )


def _build_result(
    vehicle_price: Decimal,
    residual_value: Decimal,
    n: int,
    d: Decimal,
    m: Decimal,
    f: Decimal,
    t: Decimal,
) -> ReverseQuoteResult:
    """Validate the solved lease and round the final outputs to cents.

    The breakdown is reconstructed from the full-precision solved price; only
    the returned values are rounded.
    """
    if vehicle_price <= 0:
        raise ValueError("inputs do not support a positive vehicle price")

    breakdown = _payment_breakdown(vehicle_price, residual_value, n, d, m, f, t)

    if breakdown.adjusted_cap_cost <= 0:
        raise ValueError("adjusted cap cost must be > 0 (cash down exceeds price plus fees)")
    if breakdown.adjusted_cap_cost < residual_value:
        raise ValueError("adjusted cap cost is below the residual value")
    # Equivalent to the check above for n > 0; kept as an explicit guard.
    if breakdown.monthly_depreciation < 0:
        raise ValueError("monthly depreciation is negative")

    return ReverseQuoteResult(
        vehicle_price=to_cents(vehicle_price),
        residual_value=to_cents(residual_value),
        adjusted_cap_cost=to_cents(breakdown.adjusted_cap_cost),
        total_depreciation=to_cents(breakdown.adjusted_cap_cost - residual_value),
        monthly_depreciation=to_cents(breakdown.monthly_depreciation),
        monthly_finance_charge=to_cents(breakdown.monthly_finance_charge),
        pre_tax_payment=to_cents(breakdown.pre_tax_payment),
        monthly_tax=to_cents(breakdown.monthly_tax),
        monthly_payment=to_cents(breakdown.monthly_payment),
    )


def calculate_reverse_quote_fixed_residual(
    target_monthly_payment: Number,
    term_months: int,
    cash_down: Number,
    residual_value: Number,
    money_factor: Number,
    fees: Number,
    tax_rate: Number,
) -> ReverseQuoteResult:
    """PRIMARY mode: solve for vehicle price with a fixed dollar residual.

    Raises ``TypeError`` for float/non-numeric inputs and ``ValueError`` for
    out-of-range inputs or when the inputs cannot produce a valid lease.
    """
    n, d, m, f, t = _validate_common(term_months, cash_down, money_factor, fees, tax_rate)
    target = _validate_target(target_monthly_payment)
    rv = _validate_residual_value(residual_value)

    with localcontext(prec=_PRECISION):
        # --- Reverse equation (fixed residual) -------------------------------
        # Let P = vehicle price, R = fixed residual value, n = term,
        #     MF = money factor, C = fees − cash down,
        #     T = target payment / (1 + tax rate)   (pre-tax target).
        #
        #   Adjusted cap cost = P + C
        #   T = (P + C − R)/n + (P + C + R)·MF
        #
        # Group by P, C and R:
        #   T = P·(1/n + MF) + C·(1/n + MF) − R·(1/n − MF)
        #
        # Solve:
        #
        #        P = [ T − C·(1/n + MF) + R·(1/n − MF) ] / (1/n + MF)
        #
        # ---------------------------------------------------------------------
        pre_tax_target = target / (ONE + t)
        c = f - d
        inv_n = ONE / n
        denominator = inv_n + m
        if denominator <= 0:
            raise ValueError("invalid denominator: 1/n + money_factor must be > 0")
        numerator = pre_tax_target - c * (inv_n + m) + rv * (inv_n - m)
        vehicle_price = numerator / denominator

        return _build_result(vehicle_price, rv, n, d, m, f, t)


def calculate_reverse_quote_percent_residual(
    target_monthly_payment: Number,
    term_months: int,
    cash_down: Number,
    residual_percent: Number,
    money_factor: Number,
    fees: Number,
    tax_rate: Number,
) -> ReverseQuoteResult:
    """SIMPLIFIED convenience mode: residual = residual_percent × solved price.

    The residual scales with the vehicle price being solved for. Real lender
    residuals are a percentage of MSRP (a fixed dollar amount for a given
    vehicle), so prefer ``calculate_reverse_quote_fixed_residual`` when the
    residual dollar amount is known.
    """
    n, d, m, f, t = _validate_common(term_months, cash_down, money_factor, fees, tax_rate)
    target = _validate_target(target_monthly_payment)
    r = _validate_residual_percent(residual_percent)

    with localcontext(prec=_PRECISION):
        # --- Reverse equation (percentage residual) --------------------------
        # Same symbols as the fixed mode, but R = r·P.
        #
        #   T = (P + C − r·P)/n + (P + C + r·P)·MF
        #
        # Group by P and C:
        #   T = P·[(1 − r)/n + MF·(1 + r)] + C·(1/n + MF)
        #
        # Solve:
        #
        #        P = [ T − C·(1/n + MF) ] / [ (1 − r)/n + MF·(1 + r) ]
        #
        # With 0 < r < 1 and MF ≥ 0 the denominator is always > 0.
        # ---------------------------------------------------------------------
        pre_tax_target = target / (ONE + t)
        c = f - d
        inv_n = ONE / n
        denominator = (ONE - r) * inv_n + m * (ONE + r)
        if denominator <= 0:
            raise ValueError("invalid denominator: (1 − r)/n + money_factor·(1 + r) must be > 0")
        numerator = pre_tax_target - c * (inv_n + m)
        vehicle_price = numerator / denominator

        return _build_result(vehicle_price, vehicle_price * r, n, d, m, f, t)


def calculate_reverse_quote(
    target_monthly_payment: Number,
    term_months: int,
    cash_down: Number,
    money_factor: Number,
    fees: Number,
    tax_rate: Number,
    *,
    residual_value: Number | None = None,
    residual_percent: Number | None = None,
) -> ReverseQuoteResult:
    """Dispatch to fixed-residual (primary) or percentage-residual mode.

    Pass exactly one of ``residual_value`` or ``residual_percent``.
    """
    if (residual_value is None) == (residual_percent is None):
        raise ValueError("pass exactly one of residual_value or residual_percent")
    common = {
        "target_monthly_payment": target_monthly_payment,
        "term_months": term_months,
        "cash_down": cash_down,
        "money_factor": money_factor,
        "fees": fees,
        "tax_rate": tax_rate,
    }
    if residual_value is not None:
        return calculate_reverse_quote_fixed_residual(residual_value=residual_value, **common)
    return calculate_reverse_quote_percent_residual(residual_percent=residual_percent, **common)


def calculate_implied_money_factor(
    vehicle_price: Number,
    residual_value: Number,
    term_months: int,
    target_monthly_payment: Number,
    cash_down: Number,
    fees: Number,
    tax_rate: Number,
) -> Decimal:
    """Back-solve the money factor implied by a known price, residual and payment.

    Returned at full working precision (not rounded), so it can be fed back
    into the reverse quote without losing accuracy.
    """
    n = _validate_term(term_months)
    target = _validate_target(target_monthly_payment)
    rv = _validate_residual_value(residual_value)
    p = _to_decimal("vehicle_price", vehicle_price)
    if p <= 0:
        raise ValueError("vehicle_price must be > 0")
    d = _to_decimal("cash_down", cash_down)
    f = _to_decimal("fees", fees)
    t = _to_decimal("tax_rate", tax_rate)
    if d < 0:
        raise ValueError("cash_down must be >= 0")
    if f < 0:
        raise ValueError("fees must be >= 0")
    if not (0 <= t < 1):
        raise ValueError("tax_rate must be a fraction in [0, 1) (e.g. 0.0825)")

    with localcontext(prec=_PRECISION):
        # --- Implied money factor --------------------------------------------
        # Let S = target / (1 + tax rate), C = adjusted cap cost = P + fees − down.
        #
        #   S = (C − R)/n + (C + R)·MF
        #
        # Solve:
        #
        #        MF = [ S − (C − R)/n ] / (C + R)
        #
        # ---------------------------------------------------------------------
        pre_tax_target = target / (ONE + t)
        adjusted_cap_cost = p + f - d
        if adjusted_cap_cost <= 0:
            raise ValueError("adjusted cap cost must be > 0")
        if adjusted_cap_cost < rv:
            raise ValueError("adjusted cap cost is below the residual value")
        monthly_depreciation = (adjusted_cap_cost - rv) / n
        money_factor = (pre_tax_target - monthly_depreciation) / (adjusted_cap_cost + rv)

        if money_factor < 0:
            raise ValueError("payment is below monthly depreciation; implied money factor would be negative")
        return money_factor


def calculate_monthly_payment(
    vehicle_price: Number,
    term_months: int,
    cash_down: Number,
    residual_value: Number,
    money_factor: Number,
    fees: Number,
    tax_rate: Number,
) -> Decimal:
    """Forward calculation: monthly payment (incl. tax) for a given price and
    dollar residual, rounded to cents."""
    n, d, m, f, t = _validate_common(term_months, cash_down, money_factor, fees, tax_rate)
    p = _to_decimal("vehicle_price", vehicle_price)
    rv = _validate_residual_value(residual_value)
    if p <= 0:
        raise ValueError("vehicle_price must be > 0")
    with localcontext(prec=_PRECISION):
        return to_cents(_payment_breakdown(p, rv, n, d, m, f, t).monthly_payment)
