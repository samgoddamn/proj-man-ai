# Gemensam image för API och worker. Skiljs åt enbart av command i docker-compose.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/packages:/app/apps/api

WORKDIR /app

# Beroenden först → bättre lagercache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Källkod: delad agent-kärna, API, worker, migrationer.
COPY packages ./packages
COPY apps/api ./apps/api
COPY workers ./workers
COPY alembic ./alembic
COPY alembic.ini .

# Default-kommando körs över i compose per tjänst.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
