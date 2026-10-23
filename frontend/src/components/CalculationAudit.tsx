import { formatCurrency, formatFractionAsPercent } from "../lib/decimal";
import type { QuoteResult } from "../types/quote";

interface Step {
  title: string;
  equation: string;
  note?: string;
}

/**
 * Plain-English walkthrough of the quote. Every number shown comes from the
 * backend response or the request that produced it; nothing is recomputed here.
 */
export function CalculationAudit({ result }: { result: QuoteResult }) {
  const { request: req, response: res } = result;
  const $ = formatCurrency;

  const residualNote =
    res.mode === "fixed_residual"
      ? "Residual is the fixed dollar amount you entered."
      : `Residual is ${formatFractionAsPercent(req.residual_percent ?? "0")} of the vehicle price (simplified model).`;

  const steps: Step[] = [
    {
      title: "Vehicle price + fees − cash down = adjusted cap cost",
      equation: `${$(res.vehicle_price)} + ${$(req.fees)} − ${$(req.cash_down)} = ${$(res.adjusted_cap_cost)}`,
    },
    {
      title: "Adjusted cap cost − residual value = total depreciation",
      equation: `${$(res.adjusted_cap_cost)} − ${$(res.residual_value)} = ${$(res.total_depreciation)}`,
      note: residualNote,
    },
    {
      title: "Total depreciation ÷ term = monthly depreciation",
      equation: `${$(res.total_depreciation)} ÷ ${req.term_months} months = ${$(res.monthly_depreciation)}`,
    },
    {
      title: "(Adjusted cap cost + residual value) × money factor = monthly finance charge",
      equation: `(${$(res.adjusted_cap_cost)} + ${$(res.residual_value)}) × ${req.money_factor} = ${$(res.monthly_finance_charge)}`,
    },
    {
      title: "Depreciation + finance charge = pre-tax payment",
      equation: `${$(res.monthly_depreciation)} + ${$(res.monthly_finance_charge)} = ${$(res.pre_tax_payment)}`,
    },
    {
      title: "Pre-tax payment + tax = final monthly payment",
      equation: `${$(res.pre_tax_payment)} + ${$(res.monthly_tax)} = ${$(res.monthly_payment)}`,
      note: `Tax is ${formatFractionAsPercent(req.tax_rate)} of the pre-tax payment.`,
    },
  ];

  return (
    <details className="audit">
      <summary>Show Calculation</summary>
      <p className="audit-intro">
        The vehicle price is solved directly from your target payment of {$(req.target_monthly_payment)}. Working
        forward from that price reproduces the payment:
      </p>
      <ol>
        {steps.map((step) => (
          <li key={step.title}>
            <p className="step-title">{step.title}</p>
            <p className="step-equation">{step.equation}</p>
            {step.note && <p className="step-note">{step.note}</p>}
          </li>
        ))}
      </ol>
      <p className="audit-footnote">
        Values are calculated by the server at full precision and rounded to the cent for display, so a step may
        differ from hand arithmetic on the rounded figures by $0.01.
      </p>
    </details>
  );
}
