FROM node:22-bookworm-slim AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libxrender1 libxext6 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ backend/
COPY worker/ worker/
COPY --from=web /app/frontend/dist frontend/dist
ENV PATH="/app/.venv/bin:$PATH" MPLBACKEND=Agg PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 lemon && mkdir -p /app/.data && chown -R lemon:lemon /app/.data
USER lemon
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
