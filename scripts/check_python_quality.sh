#!/usr/bin/env bash
set -euo pipefail

uv run --python 3.11 --locked --with ruff==0.16.8 \
  ruff format --check src evaluation tests

uv run --python 3.11 --locked --with ruff==0.16.8 \
  ruff check --select E4,E7,E9,F src evaluation tests
