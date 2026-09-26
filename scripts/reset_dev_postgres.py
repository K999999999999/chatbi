"""Safely recreate only this Compose project's PostgreSQL development volume."""

import argparse
import sys
from pathlib import Path

from scripts.compose_volume_reset import (
    ComposeVolumeResetError,
    configured_volume,
    reset_compose_volume,
    validate_volume_labels,
)

# Keep the existing focused helper names for unit tests and callers.
PostgresResetError = ComposeVolumeResetError


def _configured_volume(compose_config: dict[str, object]) -> tuple[str, str]:
    return configured_volume(compose_config, "postgres_data")


def _validate_volume_labels(
    labels: object,
    *,
    project_name: str,
    volume_name: str,
) -> None:
    del volume_name
    validate_volume_labels(
        labels,
        project_name=project_name,
        volume_key="postgres_data",
    )


def _reset_postgres(project_root: Path, *, confirmed: bool) -> int:
    return reset_compose_volume(
        project_root,
        service="postgres",
        volume_key="postgres_data",
        confirmation_phrase="DELETE POSTGRES DATA",
        deletion_summary="chatbi_mvp and chatbi_control development data",
        confirmed=confirmed,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="skip the interactive deletion confirmation",
    )
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    try:
        return _reset_postgres(project_root, confirmed=args.confirm)
    except (OSError, PostgresResetError) as error:
        print(f"PostgreSQL reset failed safely: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
