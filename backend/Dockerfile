# --- build stage ---
FROM python:3.11-slim AS builder

WORKDIR /app

RUN python -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install Python dependencies (deterministic, no dev extras)
COPY backend/requirements-core.txt backend/requirements-core.txt
COPY backend/requirements.txt      backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r backend/requirements.txt

# Install the hca package from source
COPY hca /app/hca
RUN pip install --no-cache-dir /app/hca

# --- runtime stage ---
FROM python:3.11-slim

WORKDIR /app

# Carry forward the pre-built venv only
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Unbuffered logs, explicit UTF-8
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Application source — only what the backend needs at runtime
COPY backend/       /app/backend/
COPY memory_service /app/memory_service/
COPY hca/           /app/hca/

# Writable storage directory (bind-mount or volume in compose)
RUN mkdir -p /app/storage/memory /app/storage/runs

# Non-root runtime user; storage is the only directory that needs write access
RUN addgroup --system hysight \
 && adduser --system --ingroup hysight --no-create-home hysight \
 && chown -R hysight:hysight /app/storage
USER hysight

EXPOSE 8000

# health-friendly startup: uvicorn serves on 0.0.0.0 so Docker/compose
# healthchecks and load-balancers can reach it
CMD ["python", "-m", "uvicorn", "backend.server:app", \
     "--host", "0.0.0.0", "--port", "8000"]
