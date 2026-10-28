FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend:/app \
    HF_HOME=/app/cache/huggingface

WORKDIR /app/backend

# Use CPU wheels instead of installing CUDA libraries on a CPU host.
RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch>=2.6,<3'

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN python -m pip install '.[deploy]'

# The serving runtimes import repository-level model definitions and verify
# bundles against the committed run records. Keep the original directory layout.
COPY ml /app/ml
COPY docs/runs /app/docs/runs
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/scripts ./scripts

# Verified bundles and database exports are supplied separately at deployment.
RUN mkdir -p /app/artifacts /app/cache/huggingface /app/backend/data

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
