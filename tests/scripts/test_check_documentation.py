from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.check_documentation import check_documentation_file


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _git_repository(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Documentation tests")


def test_valid_heading_levels_and_code_examples_pass(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    source.write_text(
        "# Title\n## Section\n### Detail\n## Back up\n"
        "`### inline example`\n\n```markdown\n#### fenced example\n§ 4.2\n```\n"
        "Setext section\n===============\n",
        encoding="utf-8",
    )

    assert check_documentation_file(tmp_path, source) == []


def test_skipped_heading_level_reports_file_and_line(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "guide.md"
    source.parent.mkdir()
    source.write_text("# Title\n### Skipped\n", encoding="utf-8")

    errors = check_documentation_file(tmp_path, source)

    assert len(errors) == 1
    assert "docs/guide.md:2" in errors[0]
    assert "heading-level" in errors[0]


def test_setext_heading_level_is_checked_at_underline_line(tmp_path: Path) -> None:
    source = tmp_path / "CONTEXT-MAP.md"
    source.write_text("# Title\n\nSecond level\n---\n#### Skipped\n", encoding="utf-8")

    errors = check_documentation_file(tmp_path, source)

    assert len(errors) == 1
    assert "CONTEXT-MAP.md:5" in errors[0]
    assert "heading-level" in errors[0]


def test_section_reference_reports_line_but_ignores_inline_and_fenced_code(
    tmp_path: Path,
) -> None:
    source = tmp_path / "AGENTS.md"
    source.write_text(
        "字面量 `§ 8.1` 可以说明符号。\n正文请参阅 § 2.3。\n~~~text\n§ 5\n~~~\n",
        encoding="utf-8",
    )

    errors = check_documentation_file(tmp_path, source)

    assert len(errors) == 1
    assert "AGENTS.md:2" in errors[0]
    assert "section-reference" in errors[0]


def test_repository_scope_checks_formal_docs_and_links_everywhere(
    tmp_path: Path,
) -> None:
    from scripts.check_documentation import check_repository

    _git_repository(tmp_path)
    (tmp_path / ".scratch").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# README\n", encoding="utf-8")
    (tmp_path / "docs" / "formal.md").write_text(
        "# Guide\n### Bad level\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "new-formal.md").write_text(
        "# Guide\n#### Bad level\n", encoding="utf-8"
    )
    (tmp_path / ".scratch" / "history.md").write_text(
        "# Old\n### Historical heading is unrestricted\n[broken](missing.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "linked-from-history.md").write_text(
        "[broken](missing.md)\n", encoding="utf-8"
    )
    (tmp_path / "ignored.md").write_text("# Ignored\n#### Skip\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.md\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md", "docs/formal.md", ".scratch/history.md")

    errors = check_repository(tmp_path)

    assert any("docs/formal.md:2" in error for error in errors)
    assert any("docs/new-formal.md:2" in error for error in errors)
    assert not any(
        ".scratch/history.md" in error and "heading-level" in error for error in errors
    )
    assert any(".scratch/history.md:3" in error for error in errors)
    assert not any("ignored.md" in error for error in errors)
    assert any("linked-from-history.md:1" in error for error in errors)


def test_combined_cli_supports_root_and_returns_nonzero_on_errors(
    tmp_path: Path,
) -> None:
    _git_repository(tmp_path)
    (tmp_path / "README.md").write_text("# Title\n### Jump\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.check_documentation", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "README.md:2" in result.stderr


def test_combined_cli_fails_without_git_repository(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.check_documentation", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "OK" not in result.stdout


def test_combined_cli_passes_valid_root(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    (tmp_path / "README.md").write_text("# Title\n## Section\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.check_documentation", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Documentation and Markdown links: OK" in result.stdout


def test_combined_cli_fails_on_text_read_error(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    (tmp_path / "README.md").write_bytes(b"# Invalid UTF-8: \xff\n")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.check_documentation", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Documentation check failed" in result.stderr
    assert "OK" not in result.stdout


def test_original_link_checker_cli_keeps_root_option(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    (tmp_path / "source.md").write_text("[missing](absent.md)\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.check_markdown_links", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing local target: absent.md" in result.stderr
