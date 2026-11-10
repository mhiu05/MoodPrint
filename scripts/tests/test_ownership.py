"""Exercise branch boundaries with real Git diffs in disposable repositories."""

import importlib.util
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

_checker_spec = importlib.util.spec_from_file_location("ownership_checker_under_test", CHECKER)
ownership = importlib.util.module_from_spec(_checker_spec)
_checker_spec.loader.exec_module(ownership)


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
            "core.excludesFile=",
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
    write(
        tmp_path,
        "backend/app/agent_gateway/wiring.py",
        'def build_runtime(cfg: AppConfig, model_client: object) -> Runtime:\n    return "baseline"\n',
    )
    write(
        tmp_path,
        "backend/app/modules/knowledge/factory.py",
        'def build_knowledge_retriever(engine, settings, cfg) -> KnowledgeRetriever:\n    return "baseline"\n',
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
        (2, "docs/implementation/compat/CC-P2-001.md"),
        (3, "docs/implementation/compat/CC-P3-001.md"),
    ],
)
def test_owned_or_generated_changes_are_accepted(repo, phase, path):
    content = "synthetic\n"
    if path == "backend/app/agent_gateway/wiring.py":
        content = 'def build_runtime(cfg: AppConfig, model_client: object) -> Runtime:\n    return "new body"\n'
    write(repo, path, content)
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


# Literal expectations come from ownership matrix section 2, independently of
# ownership.yaml and the matching helpers. One real disposable Git repository
# supplies both phase verdicts; parametrization keeps every probe visible.
OWNERSHIP_MATRIX = [
    *[
        (path, True, False)
        for path in (
            "agent/ingestion/source.py",
            "agent/src/moodprint_agent/knowledge/retriever.py",
            "agent/src/moodprint_agent/knowledge/ingest/batch.py",
            "agent/tests/knowledge/test_x.py",
            "agent/evals/knowledge/cases.jsonl",
            "backend/app/modules/knowledge/service.py",
            "backend/app/api/v1/knowledge.py",
            "backend/tests/knowledge/test_x.py",
            "backend/tests/knowledge/conftest.py",
            "backend/tests/integration/knowledge/test_x.py",
            "backend/tests/integration/knowledge/conftest.py",
            "supabase/migrations/20261108000000_kb_schema.sql",
            "supabase/tests/kb_scope.sql",
            "frontend/src/features/knowledge/index.tsx",
            "frontend/src/services/composition/knowledge.ts",
            "frontend/src/services/composition/knowledge-types.ts",
            "frontend/src/services/http/knowledge.ts",
            "frontend/src/services/http/knowledge.test.ts",
            "frontend/e2e/knowledge-real.spec.ts",
            "frontend/e2e/helpers/phase2.ts",
            "docs/implementation/reports/phase-2-report.md",
            "docs/implementation/compat/CC-P2-001.md",
        )
    ],
    *[
        (path, False, True)
        for path in (
            "agent/src/moodprint_agent/companion.py",
            "agent/src/moodprint_agent/runtime.py",
            "agent/src/moodprint_agent/events.py",
            "agent/src/moodprint_agent/budget.py",
            "agent/src/moodprint_agent/errors.py",
            "agent/src/moodprint_agent/prompts/companion.md",
            "agent/src/moodprint_agent/tools/x.py",
            "agent/src/moodprint_agent/memory/x.py",
            "agent/src/moodprint_agent/roleplay/x.py",
            "agent/src/moodprint_agent/evidence/x.py",
            "agent/src/moodprint_agent/testing/x.py",
            "agent/tests/test_x.py",
            "agent/evals/companion/cases.jsonl",
            "backend/app/agent_gateway/service.py",
            "backend/app/modules/conversations/service.py",
            "backend/app/modules/memory/service.py",
            "backend/app/modules/analysis/service.py",
            "backend/app/modules/roleplay/service.py",
            "backend/app/api/v1/conversations.py",
            "backend/app/api/v1/memories.py",
            "backend/app/api/v1/analyses.py",
            "backend/app/api/v1/roleplay.py",
            "backend/app/jobs/reconcile.py",
            "backend/tests/agent/test_x.py",
            "backend/tests/agent/conftest.py",
            "backend/tests/integration/agent/test_x.py",
            "backend/tests/integration/agent/conftest.py",
            "backend/tests/integration/test_agent_stream.py",
            "backend/tests/integration/test_agent_approval.py",
            "backend/tests/integration/test_conversations.py",
            "backend/tests/integration/test_memory.py",
            "supabase/migrations/20261108000000_ag_proposals.sql",
            "supabase/tests/ag_scope.sql",
            "frontend/src/features/ai/live/chat.tsx",
            "frontend/src/services/composition/chat.ts",
            "frontend/src/services/composition/analysis.ts",
            "frontend/src/services/composition/roleplay.ts",
            "frontend/src/services/composition/companion-types.ts",
            "frontend/src/services/http/chat-stream.ts",
            "frontend/src/services/http/analysis.test.ts",
            "frontend/src/services/http/roleplay.ts",
            "frontend/e2e/ai-real.spec.ts",
            "frontend/e2e/helpers/phase3.ts",
            "docs/implementation/reports/phase-3-report.md",
            "docs/implementation/compat/CC-P3-001.md",
        )
    ],
    *[
        (path, True, True)
        for path in (
            "uv.lock",
            "frontend/package-lock.json",
            "backend/openapi.json",
            "frontend/src/services/http/schema.gen.ts",
        )
    ],
    *[
        (path, False, False)
        for path in (
            "agent/src/moodprint_agent/context.py",
            "agent/src/moodprint_agent/__init__.py",
            "agent/src/moodprint_agent/py.typed",
            "agent/README.md",
            "shared/src/moodprint_shared/contracts/knowledge.py",
            "shared/src/moodprint_shared/testing/fixture.py",
            "shared/contract-schemas/knowledge.json",
            "shared/src/moodprint_shared/env.py",
            "shared/src/moodprint_shared/logging.py",
            "shared/tests/test_x.py",
            "shared/pyproject.toml",
            "backend/app/core/uow.py",
            "backend/app/infrastructure/engine.py",
            "backend/app/main.py",
            "backend/app/api/v1/__init__.py",
            "backend/app/modules/profiles/service.py",
            "backend/app/modules/incidents/service.py",
            "backend/app/modules/evidence/service.py",
            "backend/app/modules/plans/service.py",
            "backend/app/modules/contacts/service.py",
            "backend/app/modules/sharing/service.py",
            "backend/app/modules/support/service.py",
            "backend/app/modules/knowledge_state/service.py",
            "backend/tests/conftest.py",
            "backend/tests/integration/conftest.py",
            "backend/tests/integration/test_phase1_http.py",
            "backend/pyproject.toml",
            "supabase/migrations/20261107000000_f0_extensions_roles.sql",
            "supabase/migrations/20261107000001_f1_cases.sql",
            "supabase/tests/00_rls_coverage.sql",
            "supabase/config.toml",
            "supabase/seed.sql",
            "frontend/src/services/ports.ts",
            "frontend/src/services/composition.ts",
            "frontend/src/services/workspace.ts",
            "frontend/src/services/supabase.ts",
            "frontend/src/services/session-reset.ts",
            "frontend/src/services/mock/knowledge.ts",
            "frontend/src/services/http/client.ts",
            "frontend/src/services/http/stream-events.ts",
            "frontend/e2e/helpers/capabilities.ts",
            "frontend/e2e/responsive-real.spec.ts",
            "frontend/src/types/knowledge.ts",
            "frontend/src/app/router.tsx",
            "frontend/src/components/knowledge.tsx",
            "frontend/src/mocks/knowledge.ts",
            "frontend/src/features/home/index.tsx",
            "frontend/src/features/incidents/index.tsx",
            "frontend/src/features/profile/index.tsx",
            "frontend/src/features/support/index.tsx",
            "frontend/src/features/onboarding/index.tsx",
            "frontend/src/features/auth/index.tsx",
            "frontend/src/features/action-plans/index.tsx",
            "frontend/src/features/school-admin/index.tsx",
            "frontend/package.json",
            "scripts/x.py",
            ".github/workflows/ci.yml",
            ".githooks/pre-commit",
            "Dockerfile",
            "deploy/runtime.yaml",
            "docs/implementation/ownership.yaml",
            "docs/implementation/schema-manifest.json",
            "docs/implementation/phase2-3/11-FILE-OWNERSHIP-AND-CONTRACT-MATRIX.md",
            "docs/implementation/00-architecture.md",
            "docs/implementation/compat/CC-001.md",
            "docs/implementation/reports/pre-branch-report.md",
            "docs/implementation/reports/integration-report.md",
            ".gitignore",
            "pyproject.toml",
            ".importlinter",
            ".python-version",
            # Near misses must not broaden the four generated-file exceptions.
            "backend/openapi.json.bak",
            "backend/nested/openapi.json",
            "frontend/src/services/http/schema.gen.ts.bak",
            "frontend/src/services/http/nested/schema.gen.ts",
            "frontend/package-lock.json.bak",
            "nested/uv.lock",
            # A one-component wildcard cannot admit a nested foreign file.
            "supabase/migrations/nested/20261108000000_kb_schema.sql",
            "supabase/tests/nested/kb_scope.sql",
            "frontend/src/services/http/knowledge/nested.ts",
            "frontend/src/services/http/chat/nested.ts",
        )
    ],
]


@pytest.fixture(scope="session")
def matrix_verdicts(tmp_path_factory, seed_repo):
    matrix_repo = tmp_path_factory.mktemp("ownership-matrix")
    shutil.copytree(seed_repo, matrix_repo, dirs_exist_ok=True)
    policy = json.loads((matrix_repo / ownership.POLICY).read_text(encoding="utf-8"))
    for path, _, _ in OWNERSHIP_MATRIX:
        write(matrix_repo, path, "synthetic matrix change\n")
    verdicts = {}
    for phase in ("2", "3"):
        paths, errors = ownership.violations(matrix_repo, BASE, phase, policy)
        rejected = {json.JSONDecoder().raw_decode(error)[0] for error in errors}
        verdicts[phase] = (set(paths), rejected)
    return verdicts


@pytest.mark.parametrize("phase", ["2", "3"])
@pytest.mark.parametrize("path,p2,p3", OWNERSHIP_MATRIX, ids=[row[0] for row in OWNERSHIP_MATRIX])
def test_documented_ownership_matrix(matrix_verdicts, phase, path, p2, p3):
    observed, rejected = matrix_verdicts[phase]
    assert path in observed, "source change must be checked, never silently ignored"
    allowed = p2 if phase == "2" else p3
    assert (path not in rejected) is allowed, f"phase={phase} path={path} allowed={allowed}"


@pytest.mark.parametrize("phase", [2, 3])
@pytest.mark.parametrize("operation", ["delete", "rename"])
def test_frozen_source_cannot_escape_into_generated_file(repo, phase, operation):
    source = "backend/app/core/boundary.py"
    write(repo, source, "frozen source\n")
    git(repo, "add", source)
    git(repo, "commit", "-m", "seed frozen source")
    git(repo, "tag", "-f", BASE)
    if operation == "rename":
        git(repo, "mv", source, "uv.lock")
    else:
        git(repo, "rm", source)
    result = check(repo, phase)
    assert result.returncode == 1, result.stdout + result.stderr
    assert source in result.stdout


@pytest.mark.parametrize(
    "path,phase,name",
    [
        (FACTORY, 2, "create_retriever"),
        ("backend/app/modules/knowledge/factory.py", 2, "build_knowledge_retriever"),
        ("backend/app/agent_gateway/wiring.py", 3, "build_runtime"),
    ],
)
@pytest.mark.parametrize(
    "mutation", ["argument", "return", "async", "missing", "duplicate", "invalid"]
)
def test_all_factory_seams_reject_signature_damage(repo, path, phase, name, mutation):
    original = (repo / path).read_text(encoding="utf-8")
    if mutation == "argument":
        after = original.replace(") ->", ", *, injected: int = 1) ->")
    elif mutation == "return":
        after = original.replace(" -> KnowledgeRetriever:", " -> object:").replace(
            " -> Runtime:", " -> object:"
        )
    elif mutation == "async":
        after = original.replace("def " + name, "async def " + name)
    elif mutation == "missing":
        after = original.replace("def " + name, "def renamed_" + name)
    elif mutation == "duplicate":
        after = original + "\n" + original
    else:
        after = "def " + name + "(\n"
    write(repo, path, after)
    result = check(repo, phase)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout


@pytest.mark.parametrize("phase", [2, 3])
@pytest.mark.parametrize("path", [CONFIG, ENV, EXTRAS])
def test_deleted_shared_sections_fail_closed(repo, phase, path):
    (repo / path).unlink()
    result = check(repo, phase)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout


@pytest.mark.parametrize("phase,foreign", [(2, "AgentConfig"), (3, "KnowledgeConfig")])
def test_config_foreign_class_rejected_even_when_owned_class_also_changes(repo, phase, foreign):
    original = (repo / CONFIG).read_text(encoding="utf-8")
    after = original.replace("top_k: int = 5", "top_k: int = 7").replace(
        "max_turns: int = 8", "max_turns: int = 9"
    )
    write(repo, CONFIG, after)
    result = check(repo, phase)
    assert result.returncode == 1, f"foreign class {foreign}: {result.stdout}{result.stderr}"


@pytest.mark.parametrize(
    "path,duplicate",
    [
        (CONFIG, "\nclass KnowledgeConfig:\n    top_k: int = 9\n"),
        (ENV, "\n# --- knowledge ---\nVOYAGE_API_KEY=synthetic\n"),
    ],
)
def test_ambiguous_owned_sections_are_rejected(repo, path, duplicate):
    write(repo, path, (repo / path).read_text(encoding="utf-8") + duplicate)
    result = check(repo, 2)
    assert result.returncode == 1, result.stdout + result.stderr


def test_explicit_nonancestor_baseline_is_rejected(repo):
    ancestor = git(repo, "rev-parse", "HEAD").strip()
    write(repo, "agent/ingestion/source.py", "other line of history\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "nonancestor future baseline")
    git(repo, "tag", "baseline/unrelated")
    git(repo, "checkout", "--detach", ancestor)
    result = check(repo, base="baseline/unrelated")
    assert result.returncode == 2, result.stdout + result.stderr


@pytest.mark.parametrize(
    "path,phase",
    [
        (FACTORY, 2),
        ("backend/app/modules/knowledge/factory.py", 2),
        ("backend/app/agent_gateway/wiring.py", 3),
    ],
)
def test_all_factory_seams_accept_body_changes(repo, path, phase):
    original = (repo / path).read_text(encoding="utf-8")
    write(
        repo,
        path,
        original.replace('return "fixture"', 'return "updated"').replace(
            'return "baseline"', 'return "updated"'
        ),
    )
    result = check(repo, phase)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "path,before,after",
    [
        (ENV, "OPENAI_API_KEY=", "OPENAI_API_KEY=synthetic"),
        (EXTRAS, "companion = []", 'companion = ["foreign-package"]'),
    ],
)
def test_restored_worktree_cannot_hide_other_staged_shared_sections(repo, path, before, after):
    original = (repo / path).read_text(encoding="utf-8")
    write(repo, path, original.replace(before, after))
    git(repo, "add", path)
    write(repo, path, original)
    result = check(repo, 2)
    assert result.returncode == 1, result.stdout + result.stderr
    assert path in result.stdout


@pytest.mark.parametrize("phase", ["2", "3"])
def test_frozen_precedes_generated_and_phase_allow_rules(repo, phase):
    path = "shared/contract-schemas/knowledge.json"
    policy = json.loads((repo / ownership.POLICY).read_text(encoding="utf-8"))
    policy["generated"].append(path)
    policy["phases"][phase]["allow"].append(path)
    write(repo, path, "synthetic generated schema\n")
    paths, errors = ownership.violations(repo, BASE, phase, policy)
    assert path in paths
    assert any(path in error and "frozen" in error for error in errors)
