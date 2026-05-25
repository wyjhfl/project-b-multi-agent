FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY scripts/ scripts/
COPY data/ data/

RUN pip install --no-cache-dir -e ".[dev]"

RUN python scripts/init_demo_db.py

EXPOSE 8000

# scripts/start_app.py starts uvicorn app.main:app after demo DB init and optional Alembic migration.
CMD ["python", "scripts/start_app.py"]
