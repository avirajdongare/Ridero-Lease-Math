import type { FormEvent, ReactNode } from "react";
import type { FieldErrors, FieldName, QuoteFormValues } from "../lib/form";
import { TERMS, type ResidualMode, type Term } from "../types/quote";

interface QuoteFormProps {
  values: QuoteFormValues;
  errors: FieldErrors;
  loading: boolean;
  onChange: (values: QuoteFormValues) => void;
  onSubmit: () => void;
  onLoadExample: () => void;
}

interface FieldProps {
  name: FieldName;
  label: string;
  values: QuoteFormValues;
  errors: FieldErrors;
  onChange: (values: QuoteFormValues) => void;
  prefix?: string;
  suffix?: string;
  placeholder?: string;
  hint?: ReactNode;
}

function Field({ name, label, values, errors, onChange, prefix, suffix, placeholder, hint }: FieldProps) {
  const id = `field-${name}`;
  const error = errors[name];
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className={`input-wrap${error ? " has-error" : ""}`}>
        {prefix && <span className="affix" aria-hidden="true">{prefix}</span>}
        <input
          id={id}
          name={name}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          value={values[name]}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(event) => onChange({ ...values, [name]: event.target.value })}
        />
        {suffix && <span className="affix" aria-hidden="true">{suffix}</span>}
      </div>
      {hint && <p id={`${id}-hint`} className="hint">{hint}</p>}
      {error && <p id={`${id}-error`} className="field-error">{error}</p>}
    </div>
  );
}

export function QuoteForm({ values, errors, loading, onChange, onSubmit, onLoadExample }: QuoteFormProps) {
  const fieldProps = { values, errors, onChange };

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form className="panel quote-form" onSubmit={handleSubmit} noValidate>
      <div className="panel-header">
        <h2>Lease terms</h2>
        <button type="button" className="link-button" onClick={onLoadExample} disabled={loading}>
          Load Public Maserati Example
        </button>
      </div>

      <Field name="targetMonthlyPayment" label="Target Monthly Payment" prefix="$" placeholder="399.00" {...fieldProps} />

      <div className="field">
        <label htmlFor="field-term">Term</label>
        <select
          id="field-term"
          value={values.term}
          onChange={(event) => onChange({ ...values, term: Number(event.target.value) as Term })}
        >
          {TERMS.map((term) => (
            <option key={term} value={term}>
              {term} months
            </option>
          ))}
        </select>
      </div>

      <div className="field-row">
        <Field name="cashDown" label="Cash Down" prefix="$" placeholder="0.00" {...fieldProps} />
        <Field name="fees" label="Fees" prefix="$" placeholder="0.00" {...fieldProps} />
      </div>

      <div className="field-row">
        <Field name="moneyFactor" label="Money Factor" placeholder="0.00250" hint="e.g. 0.00250 ≈ 6% APR" {...fieldProps} />
        <Field name="taxRatePercent" label="Tax Rate" suffix="%" placeholder="0" hint="Applied to the monthly payment" {...fieldProps} />
      </div>

      <fieldset className="field residual-mode">
        <legend>Residual</legend>
        <div className="segmented">
          {(
            [
              ["fixed_residual", "Fixed Residual ($)"],
              ["percent_residual", "Residual Percentage (%)"],
            ] as [ResidualMode, string][]
          ).map(([mode, label]) => (
            <label key={mode} className={values.residualMode === mode ? "selected" : undefined}>
              <input
                type="radio"
                name="residualMode"
                value={mode}
                checked={values.residualMode === mode}
                onChange={() => onChange({ ...values, residualMode: mode })}
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>

      {values.residualMode === "fixed_residual" ? (
        <Field name="residualValue" label="Residual Value" prefix="$" placeholder="20500.00" {...fieldProps} />
      ) : (
        <Field
          name="residualPercent"
          label="Residual Percentage"
          suffix="%"
          placeholder="58"
          hint="Simplified model: residual is this percentage of the solved vehicle price."
          {...fieldProps}
        />
      )}

      <button type="submit" className="primary-button" disabled={loading} aria-busy={loading}>
        {loading ? "Calculating…" : "Calculate Max Vehicle Price"}
      </button>
    </form>
  );
}
