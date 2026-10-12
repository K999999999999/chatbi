"""Check repository links and current-document structure."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from scripts.check_markdown_links import (
    _markdown_files,
    check_repository as check_links,
)
from scripts.markdown_content import iter_markdown_lines, strip_inline_code

_ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)")
_SETEXT_HEADING = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_SECTION_REFERENCE = re.compile(r"§\s*\d+(?:\.\d+)*")
_STRUCTURAL_ROOT_FILES = {"README.md", "AGENTS.md", "CONTEXT.md", "CONTEXT-MAP.md"}


def check_documentation_file(root: Path, source: Path) -> list[str]:
    relative = source.relative_to(root).as_posix()
    errors: list[str] = []
    previous_text = ""
    previous_level: int | None = None

    def check_heading(line_number: int, level: int) -> None:
        nonlocal previous_level
        if previous_level is not None and level > previous_level + 1:
            errors.append(
                f"{relative}:{line_number}: heading-level: title jumps from "
                f"level {previous_level} to {level}; add the missing level"
            )
        previous_level = level

    markdown = source.read_text(encoding="utf-8")
    for line_number, raw_line in iter_markdown_lines(markdown):
        if raw_line is None:
            previous_text = ""
            continue
        line = strip_inline_code(raw_line)
        if _SECTION_REFERENCE.search(line):
            errors.append(
                f"{relative}:{line_number}: section-reference: replace numbered "
                "section references with a named Markdown link"
            )

        atx = _ATX_HEADING.match(line)
        if atx:
            check_heading(line_number, len(atx.group(1)))
            previous_text = ""
            continue

        setext = _SETEXT_HEADING.match(line)
        if setext and previous_text.strip():
            check_heading(line_number, 1 if setext.group(1).startswith("=") else 2)
            previous_text = ""
            continue

        previous_text = line
    return errors


def _is_structural_document(root: Path, source: Path) -> bool:
    relative = source.relative_to(root).as_posix()
    return relative in _STRUCTURAL_ROOT_FILES or (
        relative.startswith("docs/") and source.suffix.lower() == ".md"
    )


def check_repository(root: Path) -> list[str]:
    files = _markdown_files(root)
    errors = check_links(root)
    for source in files:
        if _is_structural_document(root, source):
            errors.extend(check_documentation_file(root, source))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        errors = check_repository(root)
    except (OSError, UnicodeError, subprocess.SubprocessError) as error:
        print(f"Documentation check failed: {error}", file=sys.stderr)
        return 2
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Documentation and Markdown links: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
