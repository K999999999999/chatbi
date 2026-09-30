from pathlib import Path

from scripts.check_markdown_links import check_markdown_file


def test_valid_relative_path_and_heading_anchor_pass(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("# Data Contract\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("[contract](target.md#data-contract)\n", encoding="utf-8")

    assert check_markdown_file(tmp_path, source) == []


def test_missing_path_and_anchor_report_source_and_destination(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text("# Existing\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        "[missing](absent.md)\n[anchor](target.md#absent)\n", encoding="utf-8"
    )

    errors = check_markdown_file(tmp_path, source)

    assert len(errors) == 2
    assert all("source.md:" in error for error in errors)
    assert any("absent.md" in error for error in errors)
    assert any("target.md#absent" in error for error in errors)


def test_external_links_and_fenced_examples_are_ignored(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text(
        "[site](https://example.invalid/missing)\n"
        "```markdown\n[example](does-not-exist.md#bad)\n````\n",
        encoding="utf-8",
    )

    assert check_markdown_file(tmp_path, source) == []


def test_duplicate_heading_anchor_uses_numeric_suffix(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text("# Repeat\n# Repeat\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("[second](target.md#repeat-1)\n", encoding="utf-8")

    assert check_markdown_file(tmp_path, source) == []


def test_setext_heading_is_an_anchor_but_fenced_heading_is_not(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text(
        "Setext Heading\n===============\n\n````markdown\n# Example\n````\n",
        encoding="utf-8",
    )
    source = tmp_path / "source.md"
    source.write_text(
        "[valid](target.md#setext-heading)\n[invalid](target.md#example)\n",
        encoding="utf-8",
    )

    errors = check_markdown_file(tmp_path, source)

    assert len(errors) == 1
    assert "target.md#example" in errors[0]


def test_link_cannot_escape_repository(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("[outside](../outside.md)\n", encoding="utf-8")

    errors = check_markdown_file(tmp_path, source)

    assert len(errors) == 1
    assert "escapes repository" in errors[0]
