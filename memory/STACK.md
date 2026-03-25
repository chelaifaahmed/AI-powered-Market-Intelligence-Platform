# Stack reference

## Commands (Windows)
Start API:
  .venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8099

Start dashboard (dev):
  cd dashboard && npx vite --port 5174

Build dashboard:
  cd dashboard && npm run build

Run migrations:
  .venv/Scripts/python.exe -m alembic upgrade head

Run opportunity scorer:
  .venv/Scripts/python.exe scripts/run_opportunity_scorer.py

Run RSS ingest:
  .venv/Scripts/python.exe scripts/run_rss_ingest.py

Run Trustpilot scraper:
  .venv/Scripts/python.exe scripts/run_reviews_ingest.py

Run NLP pipeline:
  .venv/Scripts/python.exe scripts/run_nlp_pipeline.py

## Key files
- API: api/main.py (~1,400 lines)
- Models: database/models.py (~1,500 lines)
- Scorer: analytics/opportunity_scorer.py
- PDF: analytics/pdf_exporter.py
- Dashboard entry: dashboard/src/App.tsx
- Design system: dashboard/src/index.css
- API client: dashboard/src/api/client.ts

## Ports
- API (dev): 8099
- Dashboard (dev): 5174
- PostgreSQL: 5432
- API (Docker): 8000
- Dashboard (Docker): 3000

## Environment variables (.env)
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
ANTHROPIC_API_KEY (for Analyst feature)
GEMINI_API_KEY (optional, for LLM extractor)
