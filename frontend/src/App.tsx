import { useRef, useState } from "react";
import { requestReverseQuote } from "./api/quote";
import { QuoteForm } from "./components/QuoteForm";
import { QuoteResults } from "./components/QuoteResults";
import { EMPTY_FORM, MASERATI_EXAMPLE, validateForm, type FieldErrors, type QuoteFormValues } from "./lib/form";
import type { QuoteResult } from "./types/quote";

function App() {
  const [values, setValues] = useState<QuoteFormValues>(EMPTY_FORM);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<QuoteResult | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  function handleLoadExample() {
    setValues(MASERATI_EXAMPLE);
    setErrors({});
    setApiError(null);
  }

  async function handleSubmit() {
    const { errors: nextErrors, request } = validateForm(values);
    setErrors(nextErrors);
    setApiError(null);
    if (!request) return;

    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setLoading(true);
    try {
      const response = await requestReverseQuote(request, controller.signal);
      setResult({ request, response });
    } catch (error) {
      if (controller.signal.aborted) return;
      setResult(null);
      setApiError(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      if (inFlight.current === controller) {
        inFlight.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Reverse Lease Quote</h1>
        <p className="subtitle">Start with a monthly payment. See the vehicle price it can support.</p>
      </header>

      <main className="layout">
        <div>
          <QuoteForm
            values={values}
            errors={errors}
            loading={loading}
            onChange={setValues}
            onSubmit={handleSubmit}
            onLoadExample={handleLoadExample}
          />
          <p className="example-note">
            Maserati example: Uses simplified assumptions derived from Ridero's public 2023 Maserati Grecale example.
            The actual lender rate and fee structure are not public.
          </p>
        </div>

        <div aria-live="polite">
          {apiError && (
            <div className="panel error-panel" role="alert">
              <p className="error-title">Couldn't calculate this quote</p>
              <p className="error-message">{apiError}</p>
            </div>
          )}
          {!apiError && result && <QuoteResults result={result} />}
          {!apiError && !result && (
            <div className="panel empty-panel">
              <p>Enter lease terms and calculate to see the maximum vehicle price.</p>
            </div>
          )}
        </div>
      </main>

      <footer className="page-footer">
        Independent proof of concept based on publicly available examples. Not affiliated with Ridero.
      </footer>
    </div>
  );
}

export default App;
