FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRAPHFLOW_DATA_DIR=/app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ ./engine/
COPY tools/ ./tools/

EXPOSE 8000

CMD ["sh", "-c", "if [ ! -d \"${GRAPHFLOW_DATA_DIR}/matrix\" ]; then python -m tools.generate_demo_corpus --out \"${GRAPHFLOW_DATA_DIR}\"; fi && uvicorn engine.api.main:app --host 0.0.0.0 --port 8000"]
