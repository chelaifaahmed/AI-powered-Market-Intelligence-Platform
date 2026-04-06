# Quick start — Docker

## Prerequisites
- Docker Desktop running

## One command
```bash
docker-compose up --build
```

## Access
- Dashboard: http://localhost:3000
- API docs:  http://localhost:8000/docs
- API health: http://localhost:8000/health

## First run
First run takes 10-15 minutes (builds images + downloads NLP model ~500 MB + seeds DB).
Subsequent runs start in ~30 seconds.

## Stop
```bash
docker-compose down
```

## Full reset (wipe database)
```bash
docker-compose down -v
```

## Troubleshooting
- If dashboard shows blank: wait 30s for API to finish seeding.
- If port 5432 conflicts: stop local PostgreSQL first.
- If port 8000 conflicts: stop local uvicorn (`taskkill /F /PID <pid>`).
