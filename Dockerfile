# syntax=docker/dockerfile:1
ARG PYTHON_BASE=mcr.microsoft.com/devcontainers/python:3-3.11-bookworm@sha256:dc2e5619a3741fe39a9d989ef8aa3ef4727e0c3cc8a6a39dc8d45822b16a0868
ARG NODE_BASE=node:24.21.0-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6
ARG POSTGRES_BASE=postgres:16-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777

FROM ${NODE_BASE} AS web-builder
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
RUN npm ci --ignore-scripts && npm cache clean --force
COPY frontend/src ./src
RUN npm run build

FROM ${NODE_BASE} AS export-builder
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.export.config.ts frontend/export.html ./
RUN npm ci --ignore-scripts && npm cache clean --force
COPY frontend/src ./src
RUN npm run build:export

FROM ${PYTHON_BASE} AS api
ARG VCS_REF=unknown
LABEL org.opencontainers.image.revision=${VCS_REF}
USER root
RUN printf 'Acquire::Retries "3";\n' > /etc/apt/apt.conf.d/80-retries \
    && sed -i '/^URIs:/ s#http://deb.debian.org#https://deb.debian.org#g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates fontconfig \
        fonts-noto-cjk=1:20220127+repack1-1 fonts-wqy-zenhei=0.9.45-8 \
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
RUN uv sync --locked --no-dev --no-install-project \
    && /opt/venv/bin/playwright install --with-deps chromium
COPY src ./src
COPY scripts/__init__.py scripts/check_dev_qdrant.py ./scripts/
COPY scripts/metadata ./scripts/metadata
COPY database ./database
COPY --from=web-builder /workspace/frontend/dist /opt/chatbi-web
COPY --from=export-builder /workspace/frontend/dist-export /opt/chatbi-export/assets
RUN /opt/venv/bin/python src/query_api/export_assets.py \
    --root /opt/chatbi-export \
    --browser-root /opt/chatbi-export/browsers \
    --chart-font-path "$(fc-match -f '%{file}' 'Noto Sans CJK SC' | head -n 1)" \
    --pdf-font-path "$(fc-match -f '%{file}' 'WenQuanYi Zen Hei' | head -n 1)" \
    --chart-font-package-version "$(dpkg-query -W -f='${Version}' fonts-noto-cjk)" \
    --pdf-font-package-version "$(dpkg-query -W -f='${Version}' fonts-wqy-zenhei)" \
    && chmod -R a-w /opt/chatbi-export /opt/chatbi-web
USER 1000:1000
EXPOSE 8000
CMD ["uvicorn", "src.query_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM ${POSTGRES_BASE} AS database
COPY database /workspace/database
COPY database/init/10_chatbi_dev_environment.sh /docker-entrypoint-initdb.d/10_chatbi_dev_environment.sh
RUN chmod 0555 /docker-entrypoint-initdb.d/10_chatbi_dev_environment.sh
