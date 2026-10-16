FROM node:22.19.0-alpine AS web
WORKDIR /web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    EDFLOW_RUN=/app/demo
WORKDIR /app

COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src/ ./src/
COPY --from=web /web/dist/ ./apps/web/dist/

RUN python -m edflow \
    --output /app/demo \
    --start 2025-01-01T00:00:00+00:00 \
    --hours 336 \
    --patients 40000 \
    --seed 42 \
    --generator-version 2 \
    --return-probability 0.1 \
    --return-risk-weighting

USER 10001:10001
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn edflow.api:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}"]