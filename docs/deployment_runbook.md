# Deployment and Demo Runbook

This runbook is for local demo and controlled internal pilot usage. It is not a public production launch guide.

## Default Boundary

- `AUTH_ENABLED=false` and `RBAC_ENABLED=false` by default for local demo.
- `MCP_MODE=fake` by default.
- Real LLM calls are disabled by default.
- SQLite is the default demo storage.
- PostgreSQL and Redis are optional pilot paths.
- Secrets, tokens, and connection-string passwords must not be printed.

## Local Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python scripts/init_demo_db.py
python scripts/start_dev.py
```

Health check:

```powershell
curl http://localhost:8000/health
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Default frontend URL: `http://localhost:3000`.

## Docker Demo

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_up.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_down.ps1
```

## Production Config Precheck

```powershell
Copy-Item .env.production.example .env
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prod_config_check.ps1
```

## Go / No-Go

- Local demo: Go.
- Controlled internal pilot: Manual Review.
- Public production direct launch: No-Go.
