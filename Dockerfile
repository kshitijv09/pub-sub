# Pub-Sub API (FastAPI + WebSocket). X-API-Key is required; set API_KEY at runtime.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY pubsub/ ./pubsub/

EXPOSE 8000

ENV PORT=8000
CMD uvicorn server:app --host 0.0.0.0 --port ${PORT}
