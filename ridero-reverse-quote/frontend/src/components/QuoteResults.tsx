import { formatCurrency } from "../lib/decimal";
import type { QuoteResult, ReverseQuoteResponse } from "../types/quote";
import { CalculationAudit } from "./CalculationAudit";

const BREAKDOWN: [keyof ReverseQuoteResponse, string][] = [
  ["residual_value", "Residual Value"],
  ["adjusted_cap_cost", "Adjusted Cap Cost"],
  ["total_depreciation", "Total Depreciation"],
  ["monthly_depreciation", "Monthly Depreciation"],
  ["monthly_finance_charge", "Monthly Finance Charge"],
  ["pre_tax_payment", "Pre-tax Payment"],
  ["monthly_tax", "Monthly Tax"],
  ["monthly_payment", "Reconstructed Monthly Payment"],
];

export function QuoteResults({ result }: { result: QuoteResult }) {
  const { response } = result;

  return (
    <section className="panel results" aria-labelledby="results-heading">
      <h2 id="results-heading" className="visually-hidden">
        Results
      </h2>
      <div className="headline">
        <p className="headline-label">Maximum Vehicle Price</p>
        <p className="headline-value">{formatCurrency(response.vehicle_price)}</p>
        <p className="headline-mode">
          {response.mode === "fixed_residual" ? "Fixed residual" : "Percentage residual (simplified model)"}
        </p>
      </div>

      <dl className="breakdown">
        {BREAKDOWN.map(([key, label]) => (
          <div key={key} className={key === "monthly_payment" ? "total" : undefined}>
            <dt>{label}</dt>
            <dd>{formatCurrency(response[key])}</dd>
          </div>
        ))}
      </dl>

      <CalculationAudit result={result} />
    </section>
  );
}
