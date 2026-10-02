"""Check source imports against the repository's documented module boundaries."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.add(module)
            if module and node.level == 0:
                imports.update(
                    f"{module}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imports


def _matches(module: str, forbidden: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden
    )


def violations(relative_path: str, imports: set[str]) -> list[str]:
    path = Path(relative_path).as_posix()
    forbidden: tuple[str, ...] = ()
    if path == "src/query_api/browser.py":
        forbidden = (
            "src.online_query",
            "src.business_analysis",
            "psycopg",
            "sqlalchemy",
            "openai",
            "langchain",
        )
    elif path == "src/query_api/app.py":
        forbidden = (
            "src.online_query.database",
            "src.online_query.llm",
            "src.online_query.query_understanding_llm",
            "src.online_query.retrieval",
            "src.online_query.sql_guard",
        )
    elif path.startswith("src/rag_offline/"):
        forbidden = ("src.query_api", "src.online_query", "psycopg", "sqlalchemy")
    matched = sorted(module for module in imports if _matches(module, forbidden))
    minimal = [
        module
        for module in matched
        if not any(
            module.startswith(f"{parent}.") for parent in matched if parent != module
        )
    ]
    return [f"{path}: forbidden dependency import `{module}`" for module in minimal]


def check_repository(root: Path) -> list[str]:
    targets = [root / "src/query_api/browser.py", root / "src/query_api/app.py"]
    rag_offline = root / "src/rag_offline"
    targets.extend(sorted(rag_offline.rglob("*.py")))
    errors: list[str] = []
    for source_path in targets:
        relative = source_path.relative_to(root).as_posix()
        try:
            imports = imported_modules(source_path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(
                f"{relative}:{exc.lineno}: cannot parse Python source: {exc.msg}"
            )
            continue
        errors.extend(violations(relative, imports))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = check_repository(args.root.resolve())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Stable module boundaries: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
