"""CI entrypoint regressions use real Git commits, not mocked ownership verdicts."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ownership_helpers", ROOT / "scripts/tests/test_ownership.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
repo = helper.repo
seed_repo = helper.seed_repo
git, write = helper.git, helper.write


def run(repo, branch, *args):
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ci_ownership.py"),
            "--repo",
            str(repo),
            "--branch",
            branch,
            *args,
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
    )


def ready(repo):
    git(repo, "tag", "baseline/phase-2-3-start-rc1")


@pytest.mark.parametrize(
    "branch,allowed,forbidden",
    [
        (
            "feat/knowledge-base",
            "backend/tests/knowledge/test_x.py",
            "agent/src/moodprint_agent/tools/x.py",
        ),
        (
            "feat/agent-companion",
            "backend/tests/agent/test_x.py",
            "agent/tests/knowledge/test_x.py",
        ),
    ],
)
def test_phase_detection_and_foreign_paths(repo, branch, allowed, forbidden):
    ready(repo)
    write(repo, allowed, "# synthetic\n")
    git(repo, "add", allowed)
    git(repo, "commit", "-m", "allowed")
    assert run(repo, branch).returncode == 0
    write(repo, forbidden, "# forbidden\n")
    git(repo, "add", forbidden)
    git(repo, "commit", "-m", "forbidden")
    assert run(repo, branch).returncode == 1


def test_missing_tag_fails_explicitly(repo):
    result = run(repo, "feat/knowledge-base")
    assert result.returncode == 2
    assert "baseline" in result.stderr.lower()


def test_retired_branch_fails_and_integrator_is_unprofiled(repo):
    assert run(repo, "feat/knowledge-ingestion-rag").returncode == 2
    assert run(repo, "integration/pre-branch-readiness").returncode == 0


@pytest.mark.parametrize("branch", ["feat/knowledge-base", "feat/agent-companion"])
def test_committed_frozen_file_fails_both_phases(repo, branch):
    ready(repo)
    write(repo, "shared/src/moodprint_shared/contracts/knowledge.py", "# frozen\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "forbidden frozen")
    assert run(repo, branch).returncode == 1


@pytest.mark.parametrize("branch", ["feat/knowledge-base", "feat/agent-companion"])
@pytest.mark.parametrize("path", [".claude/settings.local.json", ".cursor/mcp.json", ".mcp.json"])
def test_local_overrides_are_only_uncommitted_and_not_staged(repo, branch, path):
    write(repo, path, "{}\n")
    git(repo, "add", path)
    git(repo, "commit", "-m", "baseline owner config")
    ready(repo)
    write(repo, path, '{"owner":true}\n')
    assert run(repo, branch, "--local").returncode == 0
    git(repo, "add", path)
    assert run(repo, branch, "--local").returncode == 1
    git(repo, "commit", "-m", "forbidden config")
    assert run(repo, branch).returncode == 1


def test_head_commit_not_worktree_or_target_merge_is_checked(repo):
    ready(repo)
    write(repo, "agent/tests/knowledge/test_x.py", "# allowed\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "feature")
    feature = git(repo, "rev-parse", "HEAD").strip()
    write(repo, "backend/app/main.py", "# integrator target change\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "merge target")
    assert run(repo, "feat/knowledge-base", "--head", feature).returncode == 0
    assert run(repo, "feat/knowledge-base").returncode == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "badtype",
        "badphase",
        "badkind",
        "missing",
        "version",
        "badallow",
        "badsignature",
        "badsection",
        "invalidjson",
    ],
)
def test_malformed_trusted_policy_fails_closed(repo, mutation):
    path = "docs/implementation/ownership.yaml"
    policy = json.loads((repo / path).read_text())
    if mutation == "unknown":
        policy["typo_allow"] = ["**"]
    elif mutation == "badtype":
        policy["generated"] = "**"
    elif mutation == "badphase":
        policy["branches"]["feat/knowledge-base"] = "9"
    elif mutation == "badkind":
        policy["shared_sections"][".env.example"]["kind"] = "unknown_mask"
    elif mutation == "missing":
        del policy["local_overrides"]
    elif mutation == "version":
        policy["version"] = 99
    elif mutation == "badallow":
        policy["phases"]["2"]["allow"] = {"**": True}
    elif mutation == "badsignature":
        policy["frozen_signatures"]["agent/src/moodprint_agent/knowledge/__init__.py"] = (
            "create_retriever"
        )
    elif mutation == "badsection":
        policy["shared_sections"][".env.example"]["allow_all"] = True
    write(repo, path, "{" if mutation == "invalidjson" else json.dumps(policy))
    git(repo, "add", path)
    git(repo, "commit", "-m", "invalid baseline")
    ready(repo)
    assert run(repo, "feat/knowledge-base").returncode == 2


def test_policy_edit_cannot_relax_checker(repo):
    ready(repo)
    path = "docs/implementation/ownership.yaml"
    policy = json.loads((repo / path).read_text())
    policy["frozen"] = []
    policy["phases"]["2"]["allow"] = ["**"]
    write(repo, path, json.dumps(policy))
    write(repo, "backend/app/core/guard.py", "# forbidden\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "attempt relax")
    assert run(repo, "feat/knowledge-base").returncode == 1


@pytest.mark.parametrize(
    "branch,phase,allowed,foreign",
    [
        (
            "feat/knowledge-base",
            "2",
            "frontend/e2e/helpers/phase2.ts",
            "frontend/e2e/helpers/phase3.ts",
        ),
        (
            "feat/agent-companion",
            "3",
            "frontend/e2e/helpers/phase3.ts",
            "frontend/e2e/helpers/phase2.ts",
        ),
        (
            "canary/ownership/knowledge-base/matrix-green",
            "2",
            "backend/tests/integration/knowledge/test_x.py",
            "backend/tests/integration/agent/test_x.py",
        ),
        (
            "canary/ownership/agent-companion/matrix-green",
            "3",
            "backend/tests/integration/agent/test_x.py",
            "backend/tests/integration/knowledge/test_x.py",
        ),
    ],
)
def test_branch_profiles_select_the_correct_phase(repo, branch, phase, allowed, foreign):
    ready(repo)
    write(repo, allowed, "synthetic allowed\n")
    git(repo, "add", allowed)
    git(repo, "commit", "-m", "profile allowed")
    result = run(repo, branch)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"phase={phase}" in result.stdout
    write(repo, foreign, "synthetic foreign\n")
    git(repo, "add", foreign)
    git(repo, "commit", "-m", "profile foreign")
    result = run(repo, branch)
    assert result.returncode == 1, result.stdout + result.stderr
    assert foreign in result.stdout


def test_nearest_compat_baseline_accepts_merged_integrator_change(repo):
    ready(repo)
    write(repo, "backend/app/core/compat.py", "integrator compat\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "compat baseline")
    git(repo, "tag", "baseline/phase-2-3-start+cc001")
    expected_base = git(repo, "rev-parse", "HEAD").strip()
    write(repo, "agent/tests/knowledge/test_x.py", "phase change\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "feature after compat")
    result = run(repo, "feat/knowledge-base")
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"base={expected_base}" in result.stdout


def test_newer_tag_on_another_history_is_not_the_baseline(repo):
    ready(repo)
    initial = git(repo, "rev-parse", "HEAD").strip()
    write(repo, "agent/tests/knowledge/test_x.py", "phase change\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "feature")
    feature = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "checkout", "--detach", initial)
    write(repo, "backend/app/core/compat.py", "unmerged compat\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "unmerged compat baseline")
    git(repo, "tag", "baseline/phase-2-3-start+cc999")
    result = run(repo, "feat/knowledge-base", "--head", feature)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"base={initial}" in result.stdout


def test_missing_ancestor_tag_fails_even_if_matching_tag_exists_elsewhere(repo):
    initial = git(repo, "rev-parse", "HEAD").strip()
    write(repo, "backend/app/core/compat.py", "other history\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "nonancestor tagged commit")
    ready(repo)
    result = run(repo, "feat/knowledge-base", "--head", initial)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "ancestor" in result.stderr.lower()


def test_pull_head_ref_excludes_changes_from_actual_target_merge(repo):
    ready(repo)
    git(repo, "checkout", "-b", "synthetic-feature")
    write(repo, "agent/tests/knowledge/test_x.py", "feature allowed\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "feature")
    feature = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "update-ref", "refs/pull/123/head", feature)
    git(repo, "checkout", "ownership-test")
    write(repo, "backend/app/main.py", "target frozen change\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "target")
    git(repo, "merge", "--no-ff", "synthetic-feature", "-m", "synthetic PR merge")
    result = run(repo, "feat/knowledge-base", "--head", "refs/pull/123/head")
    assert result.returncode == 0, result.stdout + result.stderr
    result = run(repo, "feat/knowledge-base", "--head", "HEAD")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "backend/app/main.py" in result.stdout


def test_unknown_untracked_source_does_not_gain_local_override_exemption(repo):
    ready(repo)
    write(repo, ".cursor/mcp.json.bak", "synthetic unknown configuration\n")
    result = run(repo, "feat/knowledge-base", "--local")
    assert result.returncode == 1, result.stdout + result.stderr
    assert ".cursor/mcp.json.bak" in result.stdout
