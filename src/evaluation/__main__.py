"""运行标准回归评测并生成 JSON 数据和 Markdown 总结报告。"""

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO

from src.online_query.context import (
    DEFAULT_METRICS_PATH,
    DEFAULT_STRUCTURE_DIR,
    ContextLoadError,
    load_query_context,
)
from src.online_query.contracts import (
    QueryContext,
    QueryExecutor,
    SQLGenerator,
)
from src.online_query.database import DatabaseError, PsycopgQueryExecutor
from src.online_query.llm import LangChainSQLGenerator, LLMError
from src.online_query.service import OnlineQueryService

from .evaluator import EvaluationLoadError, load_evaluation_cases
from .reporting import (
    ReportingError,
    collect_run_metadata,
    create_report,
    load_report,
    write_markdown_report,
    write_report,
)
from .runner import run_evaluation

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = PROJECT_ROOT / "src" / "evaluation" / "eval_cases.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "evaluation"


def run_cli(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    context_loader: Callable[[], QueryContext] = load_query_context,
    generator_factory: Callable[[Mapping[str, str]], SQLGenerator] = (
        LangChainSQLGenerator.from_env
    ),
    executor_factory: Callable[[Mapping[str, str]], QueryExecutor] = (
        PsycopgQueryExecutor.from_env
    ),
    git_state_reader: Callable[[Path], tuple[str, bool]] | None = None,
    context_paths: Mapping[str, Path] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """运行一次评测；依赖参数仅用于确定性软件测试。"""

    output = sys.stdout if stdout is None else stdout
    error_output = sys.stderr if stderr is None else stderr
    source = os.environ if environ is None else environ
    parser = _parser()
    args = parser.parse_args(argv)

    try:
        cases = load_evaluation_cases(args.cases)
        baseline = load_report(args.baseline) if args.baseline else None
        context = context_loader()
        executor = executor_factory(source)
        generator = generator_factory(source)
        service = OnlineQueryService(
            generator,
            executor,
            context_loader=lambda: context,
        )
        state_reader = _read_git_state if git_state_reader is None else git_state_reader
        git_commit, git_dirty = state_reader(PROJECT_ROOT)

        run = run_evaluation(cases, service, executor, context)
        metadata = collect_run_metadata(
            run,
            git_commit=git_commit,
            git_dirty=git_dirty,
            environ=source,
            test_set_path=args.cases,
            context_paths=(
                _default_context_paths() if context_paths is None else context_paths
            ),
        )
        report = create_report(run, metadata, baseline)
        report_path = args.output_dir / f"{metadata.run_id}.json"
        summary_path = args.output_dir / f"{metadata.run_id}.md"
        write_report(report, report_path)
        write_markdown_report(report, summary_path)
        _print_summary(report, report_path, summary_path, output)
        return 0
    except (
        ContextLoadError,
        DatabaseError,
        EvaluationLoadError,
        LLMError,
        ReportingError,
    ) as exc:
        print(f"ERROR: {exc}", file=error_output)
        return 1
    except Exception:
        print("ERROR: 评测运行失败", file=error_output)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 ChatBI 标准回归评测")
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help="标准测试集路径",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="评测报告输出目录",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="明确指定的上一份有效报告",
    )
    return parser


def _read_git_state(project_root: Path) -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(project_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        raise ReportingError("Git 状态无法读取") from None
    if not commit:
        raise ReportingError("Git Commit 无法读取")
    return commit, bool(status.strip())


def _default_context_paths() -> dict[str, Path]:
    return {
        "tables": DEFAULT_STRUCTURE_DIR / "tables.json",
        "columns": DEFAULT_STRUCTURE_DIR / "columns.json",
        "relationships": DEFAULT_STRUCTURE_DIR / "relationships.json",
        "column_values": DEFAULT_STRUCTURE_DIR / "column_values.json",
        "metrics": DEFAULT_METRICS_PATH,
    }


def _print_summary(
    report: Mapping[str, object],
    report_path: Path,
    summary_path: Path,
    output: TextIO,
) -> None:
    summary = report["summary"]
    if not isinstance(summary, dict):
        raise ReportingError("报告汇总结构无效")
    accuracy = summary.get("execution_accuracy")
    accuracy_text = "N/A" if accuracy is None else f"{float(accuracy):.2%}"
    print(f"Execution Accuracy: {accuracy_text}", file=output)
    print(
        "PASS: {passed}, FAIL: {failed}, INVALID_CASE: {invalid}".format(
            passed=summary.get("passed", 0),
            failed=summary.get("failed", 0),
            invalid=summary.get("invalid_cases", 0),
        ),
        file=output,
    )
    print(f"Report: {report_path}", file=output)
    print(f"Summary Report: {summary_path}", file=output)


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
