FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY src/ /app/src/

# Install workspace dependencies from workspace root
WORKDIR /app/src
RUN uv sync --frozen --package rag-api || uv sync --package rag-api

# Set up environment
ENV PYTHONPATH=/app
WORKDIR /app/src/api

EXPOSE 8000
CMD ["/usr/local/bin/uv", "run", "uvicorn", "rag_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
