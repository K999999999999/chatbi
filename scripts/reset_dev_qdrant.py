"""Safely recreate only this Compose project's Qdrant development volume."""

import argparse
import sys
from pathlib import Path

from scripts.compose_volume_reset import (
    ComposeVolumeResetError,
    configured_volume,
    reset_compose_volume,
    validate_volume_labels,
)


def _configured_volume(compose_config: dict[str, object]) -> tuple[str, str]:
    return configured_volume(compose_config, "qdrant_data")


def _validate_volume_labels(
    labels: object,
    *,
    project_name: str,
) -> None:
    validate_volume_labels(
        labels,
        project_name=project_name,
        volume_key="qdrant_data",
    )


def _reset_qdrant(project_root: Path, *, confirmed: bool) -> int:
    return reset_compose_volume(
        project_root,
        service="qdrant",
        volume_key="qdrant_data",
        confirmation_phrase="DELETE QDRANT DATA",
        deletion_summary="Qdrant vector collections and indexes",
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
        return _reset_qdrant(project_root, confirmed=args.confirm)
    except (OSError, ComposeVolumeResetError) as error:
        print(f"Qdrant reset failed safely: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
