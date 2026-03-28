FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base AS dev
ENV UV_SYSTEM_PYTHON=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl sudo && rm -rf /var/lib/apt/lists/*
RUN sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin
COPY pyproject.toml uv.lock* ./
RUN uv export --frozen --no-hashes --group dev | uv pip install -r -
RUN useradd -m devuser && echo "devuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

FROM base AS runtime
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY src/ src/

EXPOSE 8000
CMD ["uvicorn", "src.main:build_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
