"""Check repository-local destinations in tracked Markdown files."""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_LINK = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)")
_REFERENCE = re.compile(r"^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)")
_HTML_ID = re.compile(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_HTML_NAME = re.compile(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_SETEXT_HEADING = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_INLINE_CODE = re.compile(r"(`+).*?\1")


def _markdown_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        root / path for path in result.stdout.splitlines() if (root / path).is_file()
    ]


def _slug(heading: str) -> str:
    heading = re.sub(r"`([^`]*)`", r"\1", heading)
    heading = html.unescape(heading).lower()
    heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
    return re.sub(r"\s", "-", heading)


def _anchors(markdown: str) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    previous_line = ""
    fenced: tuple[str, int] | None = None
    for line in markdown.splitlines():
        fence = _FENCE.match(line)
        if fenced:
            if (
                fence
                and fence.group(1)[0] == fenced[0]
                and len(fence.group(1)) >= fenced[1]
            ):
                fenced = None
            continue
        if fence:
            fenced = (fence.group(1)[0], len(fence.group(1)))
            previous_line = ""
            continue
        anchors.update(_HTML_ID.findall(line))
        anchors.update(_HTML_NAME.findall(line))
        heading = _HEADING.match(line)
        if heading:
            previous_line = ""
            base = _slug(heading.group(1))
        else:
            setext = _SETEXT_HEADING.match(line)
            if not setext or not previous_line.strip():
                previous_line = line
                continue
            base = _slug(previous_line.strip())
            previous_line = ""
        count = counts.get(base, 0)
        counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")
    return anchors


def _destinations(markdown: str):
    fenced: tuple[str, int] | None = None
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        fence = _FENCE.match(line)
        if fenced:
            if (
                fence
                and fence.group(1)[0] == fenced[0]
                and len(fence.group(1)) >= fenced[1]
            ):
                fenced = None
            continue
        if fence:
            fenced = (fence.group(1)[0], len(fence.group(1)))
            continue
        line = _INLINE_CODE.sub("", line)
        reference = _REFERENCE.match(line)
        if reference:
            yield line_number, reference.group(1).strip("<>")
        for match in _LINK.finditer(line):
            yield line_number, match.group(1).strip("<>")


def check_markdown_file(root: Path, source: Path) -> list[str]:
    errors: list[str] = []
    markdown = source.read_text(encoding="utf-8")
    source_rel = source.relative_to(root).as_posix()
    for line_number, destination in _destinations(markdown):
        destination = html.unescape(destination)
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc:
            continue
        path_part = unquote(parsed.path)
        target = (
            (source.parent / path_part).resolve() if path_part else source.resolve()
        )
        try:
            target.relative_to(root.resolve())
        except ValueError:
            errors.append(
                f"{source_rel}:{line_number}: target escapes repository: {destination}"
            )
            continue
        if not target.exists():
            errors.append(
                f"{source_rel}:{line_number}: missing local target: {destination}"
            )
            continue
        if parsed.fragment and target.is_file() and target.suffix.lower() == ".md":
            anchors = _anchors(target.read_text(encoding="utf-8"))
            if unquote(parsed.fragment) not in anchors:
                errors.append(
                    f"{source_rel}:{line_number}: missing anchor: {destination}"
                )
    return errors


def check_repository(root: Path) -> list[str]:
    return [
        error
        for source in _markdown_files(root)
        for error in check_markdown_file(root, source)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = check_repository(args.root.resolve())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Markdown local links: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
