/** Decimal value encoded as a string, e.g. "399.00". Never a JS number. */
export type DecimalString = string;

export type Term = 24 | 36 | 48 | 60;

export const TERMS: readonly Term[] = [24, 36, 48, 60];

export type ResidualMode = "fixed_residual" | "percent_residual";

export interface ReverseQuoteRequest {
  target_monthly_payment: DecimalString;
  term_months: Term;
  cash_down: DecimalString;
  money_factor: DecimalString;
  fees: DecimalString;
  /** Fraction, e.g. "0.0725" for 7.25%. */
  tax_rate: DecimalString;
  residual_value: DecimalString | null;
  /** Fraction, e.g. "0.58" for 58%. */
  residual_percent: DecimalString | null;
}

export interface ReverseQuoteResponse {
  mode: ResidualMode;
  vehicle_price: DecimalString;
  residual_value: DecimalString;
  adjusted_cap_cost: DecimalString;
  total_depreciation: DecimalString;
  monthly_depreciation: DecimalString;
  monthly_finance_charge: DecimalString;
  pre_tax_payment: DecimalString;
  monthly_tax: DecimalString;
  monthly_payment: DecimalString;
}

/** The request that produced a quote, kept alongside it for the audit trail. */
export interface QuoteResult {
  request: ReverseQuoteRequest;
  response: ReverseQuoteResponse;
}
