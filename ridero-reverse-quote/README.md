# ridero-reverse-quote

Reverse lease quote tool.

| Part     | Stack                         | Hosting |
| -------- | ----------------------------- | ------- |
| frontend | React + TypeScript + Vite     | Vercel  |
| backend  | Python 3.12 + FastAPI, pytest | Render  |

## Local development

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check: http://localhost:8000/health

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:5173

### Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Deployment

- **Backend (Render):** `backend/render.yaml` defines the web service (`rootDir: backend`). Set `ALLOWED_ORIGINS` to your Vercel URL.
- **Frontend (Vercel):** set the project root to `frontend`, framework preset Vite, and the env var `VITE_API_URL` to your Render URL.
