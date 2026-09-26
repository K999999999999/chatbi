"""Check the local Qdrant health endpoint without printing its API key."""

import os
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values


def _setting(name: str, default: str) -> str:
    current = os.getenv(name, "").strip()
    if current:
        return current
    values = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    configured = values.get(name)
    return configured.strip() if configured else default


def _check(
    endpoint: str,
    api_key: str,
    *,
    opener: Callable[..., object] = urlopen,
) -> None:
    request = Request(
        f"{endpoint.rstrip('/')}/healthz",
        headers={"api-key": api_key},
    )
    with opener(request, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError("Qdrant health endpoint returned a non-200 status.")


def main() -> int:
    endpoint = _setting("RAG_QDRANT_URL", "http://127.0.0.1:6333")
    api_key = _setting("QDRANT_API_KEY", "")
    if not api_key:
        print("QDRANT_API_KEY is required in .env.", file=sys.stderr)
        return 2
    try:
        _check(endpoint, api_key)
    except HTTPError as error:
        message = (
            "Qdrant rejected QDRANT_API_KEY."
            if error.code == 401
            else f"Qdrant health check failed with HTTP {error.code}."
        )
        print(message, file=sys.stderr)
        return 1
    except (OSError, URLError, RuntimeError):
        print(
            "Qdrant is unavailable. Start it with docker compose up -d qdrant.",
            file=sys.stderr,
        )
        return 1

    print("Qdrant health endpoint is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
