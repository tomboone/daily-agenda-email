FROM python:3.12-slim AS base

RUN pip install uv
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --system --frozen 2>/dev/null || uv sync --no-dev --system

FROM base AS runtime
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY src/ src/

EXPOSE 8000
CMD ["uvicorn", "src.main:build_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
