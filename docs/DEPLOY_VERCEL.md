# Deploying to Vercel

The app is already Vercel-ready. Two things were changed for serverless hosting:

1. `api/index.py` — the ASGI entrypoint Vercel looks for, which seeds the
   database at import time (Vercel does not run ASGI lifespan hooks reliably).
2. `app/config.py:resolve_db_path` — Vercel's code directory is **read-only**,
   so the SQLite file is written to `/tmp` when `data/` is not writable.

`vercel.json` bundles `app/**` and `data/**` into the function and rewrites every
route to the single ASGI app.

---

## Option A — CLI (fastest)

```bash
# Install the CLI once
npm install -g vercel

# From the project root
cd /workspace
vercel login
vercel            # first run: links/creates the project (preview deploy)
vercel --prod     # production deploy
```

The CLI prints the deployment URL, e.g. `https://ai-bi-assistant.vercel.app`.

## Option B — Git integration (best for the assessment)

1. Push the repo to GitHub (already done: `MaheshJakkala/ai-bi-assistant`).
2. Go to https://vercel.com/new and import that repository.
3. Framework preset: **Other**. Leave build command and output directory **empty**.
4. Root directory: `./`
5. Click **Deploy**.

Every later `git push` to `master` redeploys automatically.

---

## Optional: enable the LLM path

Add these in **Project → Settings → Environment Variables**, then redeploy:

| Name | Value |
| --- | --- |
| `USER_LLM_API_KEY` | your own key |
| `USER_LLM_BASE_URL` | `https://api.openai.com/v1` (or any OpenAI-compatible URL) |
| `USER_LLM_MODEL` | e.g. `gpt-4o-mini` |

Leave them unset and the app uses the offline rule-based classifier — it works
fully without any key.

> Use `USER_LLM_*` names, never `MCAI_*` or `OPENAI_API_KEY`. The prefix keeps
> project secrets separate from anything else in the environment.

---

## Verify after deploying

```bash
BASE=https://your-project.vercel.app

curl -s $BASE/api/health
curl -s -X POST $BASE/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Which product generated the highest revenue?"}'
```

Expected: `transactions_loaded: 49`, `rejected_rows: 2`, and
`Monitor generated the highest revenue: INR 473,000.00`.

Open the root URL for the UI.

---

## Things that will bite you

### 1. The database is ephemeral — this is fine

`/tmp` is per-instance and disappears when the serverless function is recycled.
Each cold start re-seeds from `data/sales_transactions.csv` in well under a
second, so **the data is always correct**; you simply don't get a persistent
writable DB. For this app (read-only analytics over a fixed CSV) that is exactly
the right trade-off.

Do **not** try to persist writes here. If the requirements grew to accept user
uploads or edits, you'd move to Postgres (Neon / Supabase / Vercel Postgres) —
say that in the interview if asked.

### 2. `/api/admin/reload` is meaningless on Vercel

It reloads the CSV into the current instance's `/tmp` database. It's harmless
but pointless on serverless; it exists for local development.

### 3. Function size limit

Vercel caps a Python function at ~250 MB unzipped (50 MB zipped on Hobby).
This app is a few MB because SQLite is in the standard library and there is no
ML dependency. Adding `pandas`/`scikit-learn` would start to matter.

### 4. No `__pycache__` in the deployment

Already excluded via `.gitignore`. Vercel installs from `requirements.txt` on
its own.

### 5. Cold starts

First request after idle takes ~1–2 s (import + seed). Subsequent requests are
fast. Not worth optimising for an assessment.

---

## Alternative: one-file Docker deploy (if Vercel fights you)

If you'd rather avoid serverless quirks entirely, a container gives you a
persistent filesystem and identical behaviour to local:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t ai-bi-assistant .
docker run -p 8000:8000 ai-bi-assistant
```

That deploys unchanged to Render, Railway, Fly.io, or Google Cloud Run — all of
which support Python natively and give you a persistent disk if you want one.
