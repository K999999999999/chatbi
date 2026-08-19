"""Technical file access for the Offline Pipeline resource inputs."""

import json
from pathlib import Path
from typing import Any


class ResourceReadError(RuntimeError):
    """Raised when an explicitly supplied resource file cannot be read."""


def read_json_file(path: Path) -> Any:
    """Read one explicitly supplied UTF-8 JSON file without discovering others."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResourceReadError(f"Unable to read JSON resource: {path}") from exc
