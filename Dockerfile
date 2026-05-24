FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY app/ app/
COPY scripts/ scripts/
COPY data/ data/

RUN pip install --no-cache-dir -e ".[dev]"

RUN python scripts/init_demo_db.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
