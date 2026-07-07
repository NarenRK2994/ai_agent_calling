# Deployment Guide

## Local setup

1. Create a Python 3.11 virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`.
4. Set Oracle, model, and runtime configuration values.
5. Run:

```powershell
python app.py
```

## Docker

Build and start the service:

```powershell
docker compose up --build
```

## Production notes

- Mount `data/` so ChromaDB persistence survives container restarts.
- Mount `logs/` so execution logs remain available outside the container.
- Point `ORACLE_CLIENT_LIB_DIR` at the Oracle Instant Client path when thick mode is required.
- Tune `ORACLE_POOL_MAX`, `ORACLE_TIMEOUT_SECONDS`, and `ERP_AGENT_RATE_LIMIT_REQUESTS` to match workload.
- Keep `ORACLE_READ_ONLY=true` for analytics-only deployments.
