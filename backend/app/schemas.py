from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, StrictInt, model_validator


def _reject_float(value: object) -> object:
    # JSON numbers with a fractional part arrive as binary floats, which can't
    # represent most cent values exactly. Require strings (or whole ints).
    if isinstance(value, float):
        raise ValueError('financial values must be sent as decimal strings, e.g. "399.00", not JSON numbers')
    if isinstance(value, bool):
        raise ValueError("financial values must be decimal strings, not booleans")
    return value


DecimalInput = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    Field(allow_inf_nan=False),
]

Money = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]


class HealthResponse(BaseModel):
    status: str


class ReverseQuoteRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "target_monthly_payment": "399.00",
                    "term_months": 36,
                    "cash_down": "0.00",
                    "money_factor": "0.00096780893",
                    "fees": "0.00",
                    "tax_rate": "0.00",
                    "residual_value": "20500.00",
                    "residual_percent": None,
                }
            ]
        },
    )

    target_monthly_payment: DecimalInput
    term_months: StrictInt
    cash_down: DecimalInput
    money_factor: DecimalInput
    fees: DecimalInput
    tax_rate: DecimalInput
    residual_value: DecimalInput | None = None
    residual_percent: DecimalInput | None = None

    @model_validator(mode="after")
    def _exactly_one_residual(self) -> "ReverseQuoteRequest":
        if (self.residual_value is None) == (self.residual_percent is None):
            raise ValueError("provide exactly one of residual_value or residual_percent")
        return self


ResidualMode = Literal["fixed_residual", "percent_residual"]


class ReverseQuoteResponse(BaseModel):
    mode: ResidualMode
    vehicle_price: Money
    residual_value: Money
    adjusted_cap_cost: Money
    total_depreciation: Money
    monthly_depreciation: Money
    monthly_finance_charge: Money
    pre_tax_payment: Money
    monthly_tax: Money
    monthly_payment: Money
