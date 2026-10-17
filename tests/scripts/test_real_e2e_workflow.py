"""执行真实工作流 shell，确认失败保留与正式 / 诊断隔离。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap


ROOT = Path(__file__).resolve().parents[2]


def workflow_script(step_id):
    lines = (ROOT / ".github/workflows/real-e2e.yml").read_text().splitlines()
    start = lines.index(f"        id: {step_id}")
    run = lines.index("        run: |", start) + 1
    end = run
    while end < len(lines) and (not lines[end] or lines[end].startswith("          ")):
        end += 1
    return textwrap.dedent("\n".join(lines[run:end]))


def run_workflow_script(tmp_path, step_id, failed_suite="", env_overrides=None):
    shim = tmp_path / "uv"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['COMMAND_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "with open(os.environ['MODEL_PATH_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(os.environ.get('RAG_MODEL_DIR')) + '\\n')\n"
        "if '-c' in args and 'DEFAULT_MODEL_DIR' in ' '.join(args):\n"
        "    print(os.environ['EXPECTED_MODEL_DIR'])\n"
        "if 'prepare-model' in args:\n"
        "    directory = Path(os.environ['RAG_MODEL_DIR'])\n"
        "    config = directory / 'config.json'\n"
        "    state = 'reuse' if config.is_file() else 'download'\n"
        "    directory.mkdir(parents=True, exist_ok=True)\n"
        "    config.touch(exist_ok=True)\n"
        "    with open(os.environ['MODEL_CACHE_LOG'], 'a') as log:\n"
        "        log.write(state + '\\n')\n"
        "sys.exit(1 if os.environ['FAILED_SUITE'] in args else 0)\n"
    )
    shim.chmod(0o700)
    env = {
        "PATH": str(tmp_path) + os.pathsep + os.defpath,
        "COMMAND_LOG": str(tmp_path / "commands.jsonl"),
        "MODEL_PATH_LOG": str(tmp_path / "model-paths.jsonl"),
        "MODEL_CACHE_LOG": str(tmp_path / "model-cache.log"),
        "FAILED_SUITE": failed_suite,
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_SHA": "a" * 40,
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        ["bash", "-c", workflow_script(step_id)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = [
        json.loads(line)
        for line in (tmp_path / "commands.jsonl").read_text().splitlines()
    ]
    return result, calls


def test_formal_failure_still_runs_all_suites_and_identity_acceptance(tmp_path):
    result, calls = run_workflow_script(tmp_path, "baseline", "--single-turn")
    assert result.returncode == 1, result.stderr
    assert len(calls) == 4
    assert "--single-turn" in calls[0]
    assert "--multi-turn" in calls[1]
    assert "--business-analysis" in calls[2]
    assert "evaluation.common.real_e2e_acceptance" in calls[3]
    assert "a" * 40 in calls[3]


def test_formal_pass_returns_success(tmp_path):
    result, calls = run_workflow_script(tmp_path, "baseline")
    assert result.returncode == 0, result.stderr
    assert len(calls) == 4


def test_identity_acceptance_failure_rejects_formal_baseline(tmp_path):
    result, calls = run_workflow_script(
        tmp_path, "baseline", "evaluation.common.real_e2e_acceptance"
    )
    assert result.returncode == 1, result.stderr
    assert len(calls) == 4


def test_diagnostic_failures_are_all_retained_and_do_not_change_formal_gate(tmp_path):
    result, calls = run_workflow_script(tmp_path, "diagnostics", "--multi-turn")
    assert result.returncode == 0, result.stderr
    assert len(calls) == 3
    assert len({call[-1] for call in calls}) == 3
    assert all("diagnostic-" in call[-1] for call in calls)
    assert (tmp_path / "summary.md").read_text().count("FAIL or unavailable") == 3


def test_model_assets_prepare_pinned_cache_before_build_and_reuse_it(tmp_path):
    model_dir = tmp_path / "model-cache" / "bge-m3-pinned"
    env = {
        "EXPECTED_MODEL_DIR": str(model_dir),
        "GITHUB_ENV": str(tmp_path / "github-env"),
    }

    first_result, first_calls = run_workflow_script(
        tmp_path, "model-assets", env_overrides=env
    )
    second_result, calls = run_workflow_script(
        tmp_path, "model-assets", env_overrides=env
    )

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert len(first_calls) == 3
    assert len(calls) == 6
    assert calls[0][-1] == (
        "from src.rag_offline.config import DEFAULT_MODEL_DIR; print(DEFAULT_MODEL_DIR)"
    )
    assert "prepare-model" in calls[1]
    assert "build-rag" in calls[2]
    assert "prepare-model" in calls[4]
    assert "build-rag" in calls[5]
    model_paths = [
        json.loads(line)
        for line in (tmp_path / "model-paths.jsonl").read_text().splitlines()
    ]
    assert model_paths[1:3] == [str(model_dir), str(model_dir)]
    assert model_paths[4:6] == [str(model_dir), str(model_dir)]
    assert (tmp_path / "model-cache.log").read_text().splitlines() == [
        "download",
        "reuse",
    ]
    assert (tmp_path / "github-env").read_text().splitlines() == [
        f"RAG_MODEL_DIR={model_dir}",
        f"RAG_MODEL_DIR={model_dir}",
    ]


def test_model_preparation_failure_stops_before_rag_build(tmp_path):
    model_dir = tmp_path / "model-cache" / "bge-m3-pinned"
    result, calls = run_workflow_script(
        tmp_path,
        "model-assets",
        failed_suite="prepare-model",
        env_overrides={
            "EXPECTED_MODEL_DIR": str(model_dir),
            "GITHUB_ENV": str(tmp_path / "github-env"),
        },
    )

    assert result.returncode != 0
    assert len(calls) == 2
    assert "prepare-model" in calls[1]
    assert all("build-rag" not in call for call in calls)
