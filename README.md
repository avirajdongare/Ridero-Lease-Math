# Ridero Reverse Quote

**Start with a monthly payment and get the most expensive vehicle that payment can lease.**

Ridero Reverse Quote flips the usual lease calculator around. A normal calculator takes a car price and returns a monthly payment. This tool takes the payment a customer can afford, along with the lease terms (term, money factor, residual, down payment, fees, tax), and returns the **maximum vehicle price** that payment supports. Every quote comes with a line-by-line breakdown so the customer and the sales team can check how the number was reached.

> **Status:** V1, a working proof of concept. It is an independent prototype built from publicly available examples and is not affiliated with Ridero.

---

## Executive summary

| | |
| --- | --- |
| **Problem** | Customers think in monthly payments, but inventory is priced in dollars. Turning "I can do $399/month" into "you can shop up to $33,000" takes repeated trial and error in a forward calculator. |
| **Solution** | A closed-form solver that computes the maximum vehicle price in one step, with no iteration and no estimating, and explains each step of the result. |
| **Accuracy** | All money math uses exact decimal arithmetic from the browser to the API to the response. Floating-point numbers are rejected at every boundary, so rounding error can't creep in. Final values are rounded to cents, half-up. |
| **Trust** | Each quote shows a plain-English calculation audit. Running the solved price back through the standard forward lease formula reproduces the target payment, and the test suite checks this. |
| **Quality** | 145 automated backend tests cover the math, the API contract, input validation and CORS. All of them pass. |
| **Deployment** | Frontend on Vercel, API on Render. Both are stateless, with no database and no stored customer data. |

### Worked example

Using Ridero's public 2023 Maserati Grecale GT example ($399/month, 36 months, $20,500 residual, nothing down, no fees, no tax):

| Output | Value |
| --- | --- |
| **Maximum vehicle price** | **$33,000.00** |
| Total depreciation | $12,500.00 |
| Monthly depreciation | $347.22 |
| Monthly finance charge | $51.78 |
| Monthly payment (check) | $399.00 |

The money factor in this example (`0.00096780893`) was back-solved from the public figures. It is **not** Ridero's actual lender rate, which isn't public.

---

## Capabilities

- **Two residual modes**
  - **Fixed residual (primary):** the residual is a dollar amount, as on a real lender rate sheet.
  - **Percentage residual (convenience):** the residual is a percentage of the solved price. Real residuals are a percentage of MSRP, so treat this mode as an approximation.
- **Supported terms:** 24, 36, 48 and 60 months.
- **Full payment breakdown:** adjusted cap cost, depreciation, finance charge, pre-tax payment, tax and total payment.
- **Calculation audit:** each step is shown with the actual numbers. The frontend displays values only and never recomputes them.
- **Clear rejection of impossible quotes:** for example, a down payment larger than price plus fees, or a payment too small to cover depreciation. These return a readable error, never a nonsense price.
- **Tax model:** tax is applied to the monthly payment, which is how most US states tax leases.

## Known limitations

These are deliberate V1 scope boundaries, not defects:

- There are no lender rate-sheet integrations. Money factor and residual are entered by hand.
- Taxing the up-front cap cost (as some states do) is not modeled.
- Acquisition and disposition fees, rebates and trade-in equity are not modeled separately. Put up-front costs in `fees`.
- The API has no authentication or rate limiting. CORS is its only access control.

---

## Architecture

```
┌──────────────────────────┐   POST /quote/reverse    ┌──────────────────────────┐
│  Frontend (Vercel)       │ ───────────────────────▶ │  API (Render)            │
│  React 18 + TypeScript   │   JSON, decimal strings  │  Python 3.12 + FastAPI   │
│  Vite                    │ ◀─────────────────────── │  Pydantic v2 · Decimal   │
└──────────────────────────┘                          └──────────────────────────┘
```

| Layer | Stack | Responsibility |
| --- | --- | --- |
| [frontend/](frontend/) | React 18, TypeScript 5.6, Vite 6 | Form input, fast client-side checks, results and audit display. Handles money as strings only. |
| [backend/](backend/) | Python 3.12, FastAPI, Pydantic v2, pytest | Final validation, the reverse lease solver, the API contract. |

The key files are:

- [backend/app/services/lease_math.py](backend/app/services/lease_math.py): the solver, with each equation derived in comments
- [backend/app/schemas.py](backend/app/schemas.py): request and response contract, plus the float-rejection rule
- [backend/app/main.py](backend/app/main.py): FastAPI app, routes and CORS
- [frontend/src/lib/decimal.ts](frontend/src/lib/decimal.ts): string-only decimal helpers, so money never becomes a JS `number`
- [frontend/src/components/CalculationAudit.tsx](frontend/src/components/CalculationAudit.tsx): the step-by-step explanation

### The math

Notation: **P** = vehicle price, **R** = residual, **n** = term in months, **MF** = money factor, **C** = fees − cash down, **T** = target payment ÷ (1 + tax rate).

The standard forward lease payment is:

```
T = (P + C − R) / n  +  (P + C + R) · MF
```

The solver rearranges it to solve for P directly:

```
Fixed residual:       P = [ T − C·(1/n + MF) + R·(1/n − MF) ] / (1/n + MF)
Percentage residual:  P = [ T − C·(1/n + MF) ] / [ (1 − r)/n + MF·(1 + r) ]     where R = r·P
```

Intermediate values are kept at 34 significant digits. Only the returned values are rounded to cents.

---

## API reference

Interactive docs (Swagger UI) are served at `/docs` on any running instance.

### `GET /health`

Liveness check, also used by Render's health check. Returns `{"status": "ok"}`.

### `POST /quote/reverse`

**All financial values must be sent as decimal strings** (`"399.00"`). Fractional JSON numbers (`399.5`) are rejected with a `422`. Whole-number JSON ints are accepted. Rates are fractions: `"0.0725"` means 7.25%.

| Field | Type | Rule |
| --- | --- | --- |
| `target_monthly_payment` | decimal string | > 0, including tax |
| `term_months` | integer | One of `24`, `36`, `48`, `60` |
| `cash_down` | decimal string | ≥ 0 |
| `money_factor` | decimal string | ≥ 0, raw factor (e.g. `"0.00250"`) |
| `fees` | decimal string | ≥ 0 |
| `tax_rate` | decimal string | Fraction in [0, 1) |
| `residual_value` | decimal string \| null | > 0. Provide **exactly one** of this or `residual_percent` |
| `residual_percent` | decimal string \| null | Fraction in (0, 1) |

Unknown fields are rejected.

**Request**

```bash
curl -X POST http://localhost:8000/quote/reverse \
  -H "Content-Type: application/json" \
  -d '{
    "target_monthly_payment": "399.00",
    "term_months": 36,
    "cash_down": "0.00",
    "money_factor": "0.00096780893",
    "fees": "0.00",
    "tax_rate": "0.00",
    "residual_value": "20500.00"
  }'
```

**Response `200`** (all money values are strings rounded to cents)

```json
{
  "mode": "fixed_residual",
  "vehicle_price": "33000.00",
  "residual_value": "20500.00",
  "adjusted_cap_cost": "33000.00",
  "total_depreciation": "12500.00",
  "monthly_depreciation": "347.22",
  "monthly_finance_charge": "51.78",
  "pre_tax_payment": "399.00",
  "monthly_tax": "0.00",
  "monthly_payment": "399.00"
}
```

**Response `422`**: both schema errors and lease-logic errors (for example, inputs that can't produce a positive price) use FastAPI's standard validation-error shape:

```json
{ "detail": [{ "type": "lease_validation_error", "loc": ["body"], "msg": "adjusted cap cost is below the residual value" }] }
```

---

## Getting started

### Prerequisites

- Python **3.12**
- Node.js **18+** and npm

### 1. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional; defaults allow http://localhost:5173
uvicorn app.main:app --reload --port 8000
```

- Health: http://localhost:8000/health
- API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:5173 and click **Load Public Maserati Example** to see a full quote.

### 3. Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

The suite covers:

- **Math** ([test_lease_math.py](backend/tests/test_lease_math.py)): hand-computed fixtures for every term and input combination; reverse-then-forward round trips; implied money factor; determinism; cent rounding; float rejection; every invalid-input path.
- **API** ([test_api.py](backend/tests/test_api.py)): both residual modes; the Maserati fixture; schema strictness (unknown fields, missing fields, floats, non-numeric strings); error shape; string serialization of money; CORS allow and deny.

To type-check and build the frontend for production, run `npm run build` in `frontend/`.

---

## Configuration

| Variable | Where | Default | Purpose |
| --- | --- | --- | --- |
| `ALLOWED_ORIGINS` | backend | `http://localhost:5173` | Comma-separated list of frontend origins allowed by CORS |
| `VITE_API_URL` | frontend (build time) | `http://localhost:8000` | Base URL of the API, without a trailing slash |

---

## Deployment

### Backend on Render

[backend/render.yaml](backend/render.yaml) defines the service as a blueprint:

- Root directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Python: `3.12.10`

Set **`ALLOWED_ORIGINS`** to the production Vercel URL, such as `https://ridero-reverse-quote.vercel.app`. Add preview URLs, comma-separated, if needed.

### Frontend on Vercel

- Root directory: `frontend`
- Framework preset: **Vite** (build `npm run build`, output `dist`)
- Environment variable: **`VITE_API_URL`** = the Render service URL

`VITE_API_URL` is baked in at build time, so redeploy the frontend after changing it.

### Release checklist

1. `pytest` passes locally.
2. `npm run build` succeeds in `frontend/`.
3. Render `ALLOWED_ORIGINS` includes the Vercel domain.
4. Vercel `VITE_API_URL` points to the Render domain.
5. After deploying, `GET /health` returns `ok` and the Maserati example returns **$33,000.00**.

---

## Repository layout

```
ridero-reverse-quote/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, routes, CORS
│   │   ├── schemas.py           # Request/response contract
│   │   └── services/
│   │       └── lease_math.py    # Reverse lease solver
│   ├── tests/                   # pytest suite (math + API)
│   ├── render.yaml              # Render blueprint
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── api/quote.ts         # API client and error mapping
    │   ├── components/          # QuoteForm, QuoteResults, CalculationAudit
    │   ├── lib/                 # decimal.ts (string math), form.ts (validation)
    │   └── types/quote.ts       # Shared request/response types
    └── vite.config.ts
```

---

## Disclaimer

This is an independent proof of concept based on publicly available examples. It is not affiliated with or endorsed by Ridero. Quotes are illustrative estimates, not offers of credit. Actual lease terms depend on the lender, the customer's credit and the jurisdiction.
