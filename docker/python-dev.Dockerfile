# syntax=docker/dockerfile:1
ARG PYTHON_BASE=mcr.microsoft.com/devcontainers/python:3-3.11-bookworm@sha256:dc2e5619a3741fe39a9d989ef8aa3ef4727e0c3cc8a6a39dc8d45822b16a0868
FROM ${PYTHON_BASE}
USER root
RUN python -m pip install --no-cache-dir uv==0.12.2
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp
WORKDIR /workspace
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
USER 1000:1000
CMD ["uvicorn", "src.query_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/workspace/src", "--reload-dir", "/workspace/scripts"]
