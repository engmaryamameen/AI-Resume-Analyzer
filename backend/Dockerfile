FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
ARG ML_RUNTIME=0
COPY backend/requirements-ml.lock /app/backend/requirements-ml.lock
RUN --mount=type=cache,id=margin-ml-pip,target=/root/.cache/pip if [ "$ML_RUNTIME" = "1" ]; then pip install -r backend/requirements-ml.lock; fi
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/requirements.lock /app/backend/requirements.lock
COPY backend/app /app/backend/app
RUN --mount=type=cache,id=margin-pip,target=/root/.cache/pip pip install -c backend/requirements.lock ./backend && useradd --uid 10001 --create-home app && mkdir -p /data/storage && chown app:app /data/storage
COPY backend/alembic /app/backend/alembic
COPY backend/alembic.ini /app/backend/alembic.ini
COPY ml /app/ml
ENV PYTHONPATH=/app/backend:/app STORAGE_DIR=/data/storage MODEL_DIR=/app/models
USER app
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
