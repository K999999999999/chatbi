# syntax=docker/dockerfile:1
ARG NODE_BASE=node:24.21.0-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6
FROM ${NODE_BASE} AS dev
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts && npm cache clean --force
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
ENV HOME=/tmp
USER node
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--configLoader", "runner"]

FROM dev AS browser
USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/browsers \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    printf 'Acquire::Retries "3";\n' > /etc/apt/apt.conf.d/80-retries \
    && npx playwright install --with-deps chromium
USER node
