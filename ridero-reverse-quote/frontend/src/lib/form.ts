import { compareDecimal, isDecimalString, isZero, normalizeDecimal, percentToFraction } from "./decimal";
import type { ResidualMode, ReverseQuoteRequest, Term } from "../types/quote";

/** Raw form state. Everything is a string exactly as the user typed it. */
export interface QuoteFormValues {
  targetMonthlyPayment: string;
  term: Term;
  cashDown: string;
  moneyFactor: string;
  fees: string;
  /** Percent, e.g. "7.25". */
  taxRatePercent: string;
  residualMode: ResidualMode;
  residualValue: string;
  /** Percent, e.g. "58". */
  residualPercent: string;
}

export type FieldName = Exclude<keyof QuoteFormValues, "term" | "residualMode">;
export type FieldErrors = Partial<Record<FieldName, string>>;

export const EMPTY_FORM: QuoteFormValues = {
  targetMonthlyPayment: "",
  term: 36,
  cashDown: "0",
  moneyFactor: "",
  fees: "0",
  taxRatePercent: "0",
  residualMode: "fixed_residual",
  residualValue: "",
  residualPercent: "",
};

// Simplified assumptions on top of Ridero's public 2023 Maserati Grecale GT
// example ($33,000 price, $20,500 residual, 36 mo, $399/mo). The money factor
// is back-solved by the backend tests; it is not Ridero's actual rate.
export const MASERATI_EXAMPLE: QuoteFormValues = {
  targetMonthlyPayment: "399",
  term: 36,
  cashDown: "0",
  moneyFactor: "0.00096780893",
  fees: "0",
  taxRatePercent: "0",
  residualMode: "fixed_residual",
  residualValue: "20500",
  residualPercent: "",
};

type Check = (value: string) => string | undefined;

const required: Check = (v) => (v === "" ? "Required" : undefined);
const decimal: Check = (v) => (isDecimalString(v) ? undefined : "Enter a number, e.g. 1250.00");
const positive: Check = (v) => (isZero(v) ? "Must be greater than 0" : undefined);
const below100: Check = (v) => (compareDecimal(v, "100") >= 0 ? "Must be less than 100" : undefined);
const atMost2Places: Check = (v) => ((v.split(".")[1] ?? "").length > 2 ? "Use at most 2 decimal places" : undefined);

function firstError(value: string, checks: Check[]): string | undefined {
  for (const check of checks) {
    const error = check(value);
    if (error) return error;
  }
  return undefined;
}

/**
 * Client-side input checks for fast feedback. The backend re-validates
 * everything and remains the source of truth.
 */
export function validateForm(values: QuoteFormValues): {
  errors: FieldErrors;
  request?: ReverseQuoteRequest;
} {
  const v = {
    targetMonthlyPayment: normalizeDecimal(values.targetMonthlyPayment),
    cashDown: normalizeDecimal(values.cashDown),
    moneyFactor: normalizeDecimal(values.moneyFactor),
    fees: normalizeDecimal(values.fees),
    taxRatePercent: normalizeDecimal(values.taxRatePercent).replace(/%$/, ""),
    residualValue: normalizeDecimal(values.residualValue),
    residualPercent: normalizeDecimal(values.residualPercent).replace(/%$/, ""),
  };

  const errors: FieldErrors = {
    targetMonthlyPayment: firstError(v.targetMonthlyPayment, [required, decimal, atMost2Places, positive]),
    cashDown: firstError(v.cashDown, [required, decimal, atMost2Places]),
    moneyFactor: firstError(v.moneyFactor, [required, decimal]),
    fees: firstError(v.fees, [required, decimal, atMost2Places]),
    taxRatePercent: firstError(v.taxRatePercent, [required, decimal, below100]),
  };
  if (values.residualMode === "fixed_residual") {
    errors.residualValue = firstError(v.residualValue, [required, decimal, atMost2Places, positive]);
  } else {
    errors.residualPercent = firstError(v.residualPercent, [required, decimal, positive, below100]);
  }

  for (const key of Object.keys(errors) as FieldName[]) {
    if (!errors[key]) delete errors[key];
  }
  if (Object.keys(errors).length > 0) return { errors };

  return {
    errors,
    request: {
      target_monthly_payment: v.targetMonthlyPayment,
      term_months: values.term,
      cash_down: v.cashDown,
      money_factor: v.moneyFactor,
      fees: v.fees,
      tax_rate: percentToFraction(v.taxRatePercent),
      residual_value: values.residualMode === "fixed_residual" ? v.residualValue : null,
      residual_percent: values.residualMode === "percent_residual" ? percentToFraction(v.residualPercent) : null,
    },
  };
}
