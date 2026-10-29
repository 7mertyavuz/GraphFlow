FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRAPHFLOW_DATA_DIR=/app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ ./engine/
COPY tools/ ./tools/
COPY data/f3/ ./data/f3/

EXPOSE 8000

CMD ["uvicorn", "engine.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
