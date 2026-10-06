# syntax=docker/dockerfile:1
ARG PYTHON_BASE=mcr.microsoft.com/devcontainers/python:3-3.11-bookworm@sha256:dc2e5619a3741fe39a9d989ef8aa3ef4727e0c3cc8a6a39dc8d45822b16a0868
ARG NODE_BASE=node:24.21.0-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6

FROM ${NODE_BASE} AS export-builder
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.export.config.ts frontend/export.html ./
RUN npm ci --ignore-scripts && npm cache clean --force
COPY frontend/src ./src
RUN npm run build:export

FROM ${PYTHON_BASE}
USER root
RUN printf 'Acquire::Retries "3";\n' > /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates fontconfig fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
RUN /usr/local/bin/python -m pip install --no-cache-dir uv==0.12.2
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    CHATBI_EXPORT_ROOT=/opt/chatbi-export \
    PLAYWRIGHT_BROWSERS_PATH=/opt/chatbi-export/browsers
WORKDIR /workspace
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
RUN uv run playwright install --with-deps chromium
COPY --from=export-builder /workspace/frontend/dist-export /opt/chatbi-export/assets
COPY src/query_api/export_assets.py /opt/chatbi-export/export_assets.py
RUN uv run python /opt/chatbi-export/export_assets.py \
    --root /opt/chatbi-export \
    --browser-root /opt/chatbi-export/browsers \
    --font-path "$(fc-match -f '%{file}' 'Noto Sans CJK SC' | head -n 1)" \
    && chmod -R a-w /opt/chatbi-export
USER 1000:1000
CMD ["uvicorn", "src.query_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/workspace/src", "--reload-dir", "/workspace/scripts"]
