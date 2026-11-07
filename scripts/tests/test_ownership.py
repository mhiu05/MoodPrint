"""Exercise branch boundaries with real Git diffs in disposable repositories."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_ownership.py"
POLICY = ROOT / "docs" / "implementation" / "ownership.yaml"
BASE = "baseline/phase-1-verified"
CONFIG = "shared/src/moodprint_shared/config.py"
ENV = ".env.example"
EXTRAS = "agent/pyproject.toml"
FACTORY = "agent/src/moodprint_agent/knowledge/__init__.py"


def git(repo, *args):
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Ownership test",
            "-c",
            "user.email=ownership@example.test",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=" + str(repo / "no-hooks"),
            "-C",
            str(repo),
            *args,
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    ).stdout


def write(repo, path, content):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.fixture(scope="session")
def seed_repo(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("ownership-seed")
    git(tmp_path, "init", "-b", "ownership-test")
    write(tmp_path, "docs/implementation/ownership.yaml", POLICY.read_text(encoding="utf-8"))
    write(
        tmp_path,
        CONFIG,
        "from dataclasses import dataclass\n\n"
        "@dataclass(frozen=True)\nclass KnowledgeConfig:\n    top_k: int = 5\n\n"
        "@dataclass(frozen=True)\nclass AgentConfig:\n    max_turns: int = 8\n\n"
        "@dataclass(frozen=True)\nclass MemoryConfig:\n    stale_days: int = 90\n\n"
        "class ApiConfig:\n    pool_size: int = 5\n",
    )
    write(
        tmp_path,
        ENV,
        "# --- runtime ---\nAPP_ENV=test\n"
        "# --- knowledge ---\nVOYAGE_API_KEY=\n"
        "# --- agent ---\nOPENAI_API_KEY=\n"
        "# --- frontend ---\nVITE_PUBLIC_API_URL=\n",
    )
    write(
        tmp_path,
        EXTRAS,
        '[project]\nname = "test-agent"\n'
        "[project.optional-dependencies]\n# knowledge extra\nknowledge = []\n"
        "# companion extra\ncompanion = []\n[build-system]\nrequires = []\n",
    )
    write(
        tmp_path,
        FACTORY,
        'def create_retriever(cfg: AppConfig) -> KnowledgeRetriever:\n    return "fixture"\n',
    )
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "synthetic baseline")
    git(tmp_path, "tag", BASE)
    return tmp_path


@pytest.fixture
def repo(tmp_path, seed_repo):
    shutil.copytree(seed_repo, tmp_path, dirs_exist_ok=True)
    return tmp_path


def check(repo, phase=2, base=BASE):
    return subprocess.run(
        [sys.executable, str(CHECKER), "--phase", str(phase), "--base", base, "--repo", str(repo)],
        text=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        check=False,
    )


@pytest.mark.parametrize(
    ("phase", "path"),
    [
        (2, "agent/ingestion/source.py"),
        (2, "agent/src/moodprint_agent/knowledge/retriever.py"),
        (2, "agent/tests/knowledge/test_adapter.py"),
        (2, "agent/evals/knowledge/cases.jsonl"),
        (2, "backend/app/modules/knowledge/service.py"),
        (2, "backend/app/api/v1/knowledge.py"),
        (2, "supabase/migrations/20261108000000_kb_sources.sql"),
        (2, "supabase/tests/kb_scope.sql"),
        (2, "frontend/src/features/knowledge/index.tsx"),
        (2, "frontend/src/services/composition/knowledge.ts"),
        (2, "frontend/src/services/http/knowledge.ts"),
        (2, "docs/implementation/reports/phase-2-report.md"),
        (3, "agent/src/moodprint_agent/runtime.py"),
        (3, "agent/src/moodprint_agent/prompts/companion.md"),
        (3, "agent/src/moodprint_agent/tools/knowledge_search.py"),
        (3, "agent/src/moodprint_agent/memory/session.py"),
        (3, "agent/src/moodprint_agent/roleplay/runtime.py"),
        (3, "agent/src/moodprint_agent/evidence/analysis.py"),
        (3, "agent/tests/integration/test_memory.py"),
        (3, "agent/evals/companion/cases.jsonl"),
        (3, "backend/app/agent_gateway/wiring.py"),
        (3, "backend/app/modules/conversations/service.py"),
        (3, "backend/app/modules/memory/service.py"),
        (3, "backend/app/api/v1/conversations.py"),
        (3, "backend/app/api/v1/memories.py"),
        (3, "backend/app/jobs/reconcile.py"),
        (3, "supabase/migrations/20261108000000_ag_roleplay.sql"),
        (3, "supabase/tests/ag_scope.sql"),
        (3, "frontend/src/features/ai/chat.tsx"),
        (3, "frontend/src/services/composition/analysis.ts"),
        (3, "frontend/src/services/http/roleplay.ts"),
        (3, "docs/implementation/reports/phase-3-report.md"),
        (2, "uv.lock"),
        (3, "frontend/package-lock.json"),
        (2, "backend/openapi.json"),
        (3, "frontend/src/services/http/schema.gen.ts"),
        (2, "docs/implementation/compat/CC-001.md"),
        (3, "docs/implementation/compat/CC-002.md"),
    ],
)
def test_owned_or_generated_changes_are_accepted(repo, phase, path):
    write(repo, path, "synthetic\n")
    result = check(repo, phase)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("phase", "path"),
    [
        (2, "agent/src/moodprint_agent/runtime.py"),
        (2, "agent/tests/test_companion.py"),
        (3, "agent/src/moodprint_agent/knowledge/retriever.py"),
        (3, "agent/tests/knowledge/test_adapter.py"),
        (3, "agent/evals/knowledge/cases.jsonl"),
        (2, "supabase/migrations/20261108000000_ag_roleplay.sql"),
        (3, "supabase/migrations/20261108000000_kb_sources.sql"),
        (2, "supabase/migrations/nested/20261108000000_kb_sources.sql"),
        (2, "shared/src/moodprint_shared/contracts/knowledge.py"),
        (3, "shared/src/moodprint_shared/testing/knowledge_fixture.py"),
        (2, "shared/contract-schemas/knowledge.json"),
        (3, "shared/src/moodprint_shared/env.py"),
        (2, "shared/src/moodprint_shared/logging.py"),
        (2, "supabase/migrations/20261107000000_f0_profiles.sql"),
        (3, "supabase/migrations/20261107000000_f1_cases.sql"),
        (2, "backend/app/core/uow.py"),
        (3, "backend/app/modules/evidence/service.py"),
        (2, "frontend/src/services/ports.ts"),
        (3, "frontend/src/services/http/client.ts"),
        (2, "frontend/src/services/workspace.ts"),
        (3, "frontend/src/services/http/stream-events.ts"),
        (2, "frontend/src/services/composition.ts"),
        (3, "agent/pyproject-extra.toml"),
        (2, "backend/app/main.py"),
        (3, ".env"),
        (2, ".gitignore"),
    ],
)
def test_frozen_foreign_and_unowned_changes_are_rejected(repo, phase, path):
    write(repo, path, "synthetic\n")
    result = check(repo, phase)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout


@pytest.mark.parametrize("state", ["committed", "staged", "unstaged", "untracked", "deleted"])
def test_checks_all_git_states_against_baseline(repo, state):
    path = "backend/app/core/new_guard.py"
    write(repo, path, "before\n")
    if state != "untracked":
        git(repo, "add", path)
        git(repo, "commit", "-m", "add frozen guard")
        if state != "committed":
            git(repo, "tag", "-f", BASE)
    if state == "deleted":
        (repo / path).unlink()
    elif state in {"staged", "unstaged"}:
        write(repo, path, "after\n")
        if state == "staged":
            git(repo, "add", path)
    result = check(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout


def test_restored_worktree_cannot_hide_staged_frozen_change(repo):
    path = "backend/app/core/staged.py"
    write(repo, path, "staged forbidden change\n")
    git(repo, "add", path)
    (repo / path).unlink()
    result = check(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout


def test_restored_worktree_cannot_hide_staged_foreign_section(repo):
    original = (repo / CONFIG).read_text()
    write(repo, CONFIG, original.replace("max_turns: int = 8", "max_turns: int = 99"))
    git(repo, "add", CONFIG)
    write(repo, CONFIG, original)
    result = check(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert CONFIG in result.stdout


def test_rename_cannot_hide_frozen_source(repo):
    path = "backend/app/core/frozen.py"
    write(repo, path, "original\n")
    git(repo, "add", path)
    git(repo, "commit", "-m", "frozen source")
    git(repo, "tag", "-f", BASE)
    write(repo, "agent/ingestion/moved.py", "original\n")
    (repo / path).unlink()
    git(repo, "add", ".")
    result = check(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout


@pytest.mark.parametrize(
    ("phase", "before", "after"),
    [
        (2, "top_k: int = 5", "top_k: int = 7"),
        (3, "max_turns: int = 8", "max_turns: int = 9"),
        (3, "stale_days: int = 90", "stale_days: int = 60"),
    ],
)
def test_phase_can_change_only_owned_config_classes(repo, phase, before, after):
    write(repo, CONFIG, (repo / CONFIG).read_text().replace(before, after))
    result = check(repo, phase)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("phase", [2, 3])
def test_config_edit_cannot_hide_changes_outside_owned_class(repo, phase):
    write(
        repo,
        CONFIG,
        (repo / CONFIG).read_text().replace("pool_size: int = 5", "pool_size: int = 99"),
    )
    result = check(repo, phase)
    assert result.returncode == 1, result.stdout + result.stderr
    assert CONFIG in result.stdout


@pytest.mark.parametrize(("phase", "setting"), [(2, "VOYAGE_API_KEY="), (3, "OPENAI_API_KEY=")])
def test_phase_can_change_owned_env_block(repo, phase, setting):
    write(repo, ENV, (repo / ENV).read_text().replace(setting, setting + "synthetic-example"))
    result = check(repo, phase)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "synthetic-example" not in result.stdout + result.stderr


@pytest.mark.parametrize("phase", [2, 3])
def test_env_edit_cannot_change_runtime_or_section_markers(repo, phase):
    write(repo, ENV, (repo / ENV).read_text().replace("APP_ENV=test", "APP_ENV=production"))
    result = check(repo, phase)
    assert result.returncode == 1, result.stdout + result.stderr
    write(
        repo, ENV, git(repo, "show", BASE + ":" + ENV).replace("# --- knowledge ---", "# knowledge")
    )
    assert check(repo, phase).returncode == 1


@pytest.mark.parametrize(("phase", "extra"), [(2, "knowledge"), (3, "companion")])
def test_phase_can_change_only_owned_multiline_extra(repo, phase, extra):
    write(
        repo,
        EXTRAS,
        (repo / EXTRAS)
        .read_text()
        .replace(extra + " = []", extra + ' = [\n  "synthetic-package>=1",\n]'),
    )
    result = check(repo, phase)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(("phase", "extra"), [(2, "companion"), (3, "knowledge")])
def test_foreign_extra_and_unrelated_toml_changes_are_rejected(repo, phase, extra):
    write(
        repo,
        EXTRAS,
        (repo / EXTRAS).read_text().replace(extra + " = []", extra + ' = ["forbidden"]'),
    )
    assert check(repo, phase).returncode == 1
    write(
        repo,
        EXTRAS,
        git(repo, "show", BASE + ":" + EXTRAS).replace('name = "test-agent"', 'name = "changed"'),
    )
    assert check(repo, phase).returncode == 1


def test_factory_body_is_owned_but_signature_is_frozen(repo):
    original = (repo / FACTORY).read_text()
    write(repo, FACTORY, original.replace('return "fixture"', 'return "real"'))
    result = check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    write(repo, FACTORY, original.replace("cfg: AppConfig", "cfg: AppConfig, timeout: int = 1"))
    result = check(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert FACTORY in result.stdout


def test_policy_cannot_be_relaxed_in_feature_branch(repo):
    path = "docs/implementation/ownership.yaml"
    policy = json.loads((repo / path).read_text())
    policy["frozen"] = []
    policy["phases"]["2"]["allow"].append("**")
    write(repo, path, json.dumps(policy))
    write(repo, "backend/app/core/uow.py", "forbidden\n")
    result = check(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout
    assert "backend/app/core/uow.py" in result.stdout


def test_missing_baseline_fails_without_reading_env_or_creating_tag(repo):
    result = check(repo, base="baseline/not-created")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "baseline" in result.stdout + result.stderr
    assert "baseline/not-created" not in git(repo, "tag", "--list")


def test_clean_tree_passes_without_claiming_phase_gates(repo):
    result = check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 changed" in result.stdout
    assert "G2 PASS" not in result.stdout


@pytest.mark.parametrize(
    "path",
    [
        "backend/app/core/__pycache__/uow.cpython-312.pyc",
        ".local/test.env",
        "frontend/node_modules/synthetic/index.js",
        "frontend/test-results/.last-run.json",
        "frontend/dist/assets/index.js",
        "supabase/.branches/_current_branch",
    ],
)
def test_untracked_runtime_artifacts_are_not_source_changes(repo, path):
    write(repo, path, "synthetic generated output\n")
    result = check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 changed" in result.stdout


@pytest.mark.parametrize(
    "path", ["backend/app/core/__pycache__/uow.cpython-312.pyc", ".local/output.json"]
)
def test_tracked_runtime_artifact_changes_still_require_ownership(repo, path):
    write(repo, path, "baseline generated output\n")
    git(repo, "add", path)
    git(repo, "commit", "-m", "tracked artifact for boundary regression")
    git(repo, "tag", "-f", BASE)
    write(repo, path, "changed generated output\n")
    result = check(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout


def test_new_frozen_cache_source_is_not_a_bytecode_exemption(repo):
    path = "backend/app/core/__pycache__/source.py"
    write(repo, path, "forbidden source\n")
    result = check(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout
