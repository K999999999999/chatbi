#!/usr/bin/env python3
"""Run the GitHub Actions auto-merge step against mocked PR states."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path

import yaml


WORKFLOW = Path(__file__).parents[3] / ".github" / "workflows" / "enable-auto-merge.yml"
DOCUMENT = yaml.safe_load(WORKFLOW.read_text())
SCRIPT = DOCUMENT["jobs"]["enable-auto-merge"]["steps"][0]["run"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print("PASS:", message)


syntax = subprocess.run(["bash", "-n"], input=SCRIPT, text=True, capture_output=True)
require(syntax.returncode == 0, "embedded Bash syntax")

base_pr = {
    "state": "open",
    "draft": False,
    "head": {"sha": "abc123", "repo": {"full_name": "K999999999999/chatbi"}},
    "base": {"ref": "master"},
}
fake_gh = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    if args[:2] == ["pr", "view"]:
        print(os.environ.get("FAKE_AUTO", "false"))
    elif args[:1] == ["api"]:
        if os.environ.get("FAKE_API_FAIL") == "true": sys.exit(9)
        pr = json.loads(os.environ["FAKE_PR_JSON"])
        fields = [pr["state"], str(pr["draft"]).lower(), pr["head"]["sha"], pr["base"]["ref"], (pr["head"].get("repo") or {}).get("full_name", "")]
        print("\\t".join(fields))
    elif args[:2] == ["pr", "merge"]:
        with open(os.environ["MERGE_MARKER"], "w") as marker: marker.write("called")
    else:
        sys.exit(88)
    """
)

cases = [
    ("eligible current PR", {}, "false", False, 0, True),
    ("unresolved dependency remains Draft", {"draft": True}, "false", False, 0, False),
    ("wrong stacked-PR base", {"base": {"ref": "feature/parent"}}, "false", False, 0, False),
    ("live head changed after event", {"head": {"sha": "def456", "repo": {"full_name": "K999999999999/chatbi"}}}, "false", False, 0, False),
    ("fork PR", {"head": {"sha": "abc123", "repo": {"full_name": "someone/chatbi"}}}, "false", False, 0, False),
    ("closed PR", {"state": "closed"}, "false", False, 0, False),
    ("event is Draft", {}, "false", True, 0, False),
    ("event base is not master", {}, "false", False, 0, False),
    ("live status query fails", {}, "false", False, 9, False),
    ("auto-merge already enabled", {}, "true", False, 0, False),
]

with tempfile.TemporaryDirectory(prefix="auto-merge-workflow-fixture-") as directory:
    temporary = Path(directory)
    gh = temporary / "gh"
    gh.write_text(fake_gh)
    gh.chmod(0o755)

    for index, (name, delta, auto_enabled, event_draft, expected_code, should_merge) in enumerate(cases):
        pr = json.loads(json.dumps(base_pr))
        pr.update(delta)
        marker = temporary / f"merge-{index}"
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": f"{temporary}:{environment['PATH']}",
                "GITHUB_REPOSITORY": "K999999999999/chatbi",
                "PR_URL": "https://github.com/K999999999999/chatbi/pull/123",
                "PR_NUMBER": "123",
                "EVENT_HEAD_SHA": "abc123",
                "EVENT_HEAD_REPO": "K999999999999/chatbi",
                "EVENT_BASE_REF": "master" if name != "event base is not master" else "release",
                "EVENT_DRAFT": "true" if event_draft else "false",
                "FAKE_PR_JSON": json.dumps(pr),
                "FAKE_AUTO": auto_enabled,
                "FAKE_API_FAIL": "true" if name == "live status query fails" else "false",
                "MERGE_MARKER": str(marker),
            }
        )
        result = subprocess.run(["bash", "-c", SCRIPT], env=environment, text=True, capture_output=True)
        merge_called = marker.exists()
        require(result.returncode == expected_code, f"{name}: expected exit {expected_code}, got {result.returncode}")
        require(merge_called == should_merge, f"{name}: merge action expectation")

print(f"PASS: {len(cases)} mocked GitHub PR states")
