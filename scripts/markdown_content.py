"""Small Markdown line helpers shared by repository documentation checks."""

from __future__ import annotations

import re
from collections.abc import Iterator

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"(`+).*?\1")


def iter_markdown_lines(markdown: str) -> Iterator[tuple[int, str | None]]:
    """Yield source line numbers, using None for fenced-code lines."""
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
            yield line_number, None
            continue
        if fence:
            fenced = (fence.group(1)[0], len(fence.group(1)))
            yield line_number, None
            continue
        yield line_number, line


def strip_inline_code(line: str) -> str:
    """Remove inline code spans while preserving the surrounding text."""
    return _INLINE_CODE.sub("", line)
