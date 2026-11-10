"""Enforce Phase 2/3 ownership from the trusted baseline; never read actual env files.

Usage: python scripts/check_ownership.py --phase 2 --base baseline/phase-1-verified
Exit 0 means ownership passed, 1 means violations, 2 means the check could not run.
This check does not assert G1/G2 readiness, create tags, or validate SQL object scope.
"""

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = "docs/implementation/ownership.yaml"
DEFAULT_BASE = "baseline/phase-2-3-start"


class CheckError(Exception):
    """A prerequisite is missing, without exposing file contents or Git stderr."""


class SectionError(Exception):
    """An owned section is missing, ambiguous or invalid."""


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if result.returncode:
        raise CheckError("Git check failed; verify the repository and baseline reference.")
    return result.stdout


def assert_base_ancestor(repo: Path, base_commit: str, head: str) -> None:
    """Fail closed unless the selected baseline commit is an ancestor of head.

    `git describe` already limits the implicit tag search to ancestors. An
    explicit --base can name any commit, including a future or unrelated one,
    and must not become the policy source for this revision.
    """
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            "--end-of-options",
            base_commit,
            head,
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise CheckError("Explicit baseline is not an ancestor of the checked revision.")


def baseline_text(repo: Path, commit: str, path: str) -> str:
    try:
        return git(repo, "show", f"{commit}:{path}").decode("utf-8").replace("\r\n", "\n")
    except (CheckError, UnicodeError):
        raise CheckError(f"Baseline is missing a readable required file: {path}") from None


def resolve_base(repo: Path, head: str = "HEAD") -> str:
    try:
        tag = (
            git(
                repo,
                "describe",
                "--tags",
                "--match",
                "baseline/phase-2-3-start*",
                "--abbrev=0",
                head,
            )
            .decode()
            .strip()
        )
        return (
            git(repo, "rev-parse", "--verify", "--end-of-options", tag + "^{commit}")
            .decode()
            .strip()
        )
    except CheckError:
        raise CheckError(
            "Missing ancestor baseline/phase-2-3-start* tag; fetch verified tags."
        ) from None


def validate_policy(policy: dict) -> None:
    required = {
        "version",
        "source",
        "baseline",
        "branches",
        "retired_branches",
        "local_overrides",
        "frozen",
        "generated",
        "untracked_artifacts",
        "shared_sections",
        "frozen_signatures",
        "phases",
    }
    if not isinstance(policy, dict) or set(policy) != required or policy["version"] != 2:
        raise CheckError("Unknown, missing or unsupported ownership policy configuration.")

    def strings(value):
        return isinstance(value, list) and all(isinstance(item, str) and item for item in value)

    for key in (
        "frozen",
        "generated",
        "untracked_artifacts",
        "retired_branches",
        "local_overrides",
    ):
        if not strings(policy[key]):
            raise CheckError("Ownership policy lists must contain nonempty strings.")
    if not isinstance(policy["source"], str) or not isinstance(policy["baseline"], str):
        raise CheckError("Invalid ownership policy metadata.")
    branches = policy["branches"]
    if not isinstance(branches, dict) or branches != {
        "feat/knowledge-base": "2",
        "feat/agent-companion": "3",
    }:
        raise CheckError("Invalid ownership branch profiles.")
    if not isinstance(policy["phases"], dict) or set(policy["phases"]) != {"2", "3"}:
        raise CheckError("Invalid ownership phases.")
    for rules in policy["phases"].values():
        if (
            not isinstance(rules, dict)
            or set(rules) != {"allow", "exclude"}
            or not all(strings(v) for v in rules.values())
        ):
            raise CheckError("Invalid phase path rules.")
    if not isinstance(policy["shared_sections"], dict) or not isinstance(
        policy["frozen_signatures"], dict
    ):
        raise CheckError("Invalid shared section or signature rules.")
    for rule in policy["shared_sections"].values():
        if (
            not isinstance(rule, dict)
            or set(rule) != {"kind", "2", "3"}
            or rule["kind"] not in MASKERS
            or not strings(rule["2"])
            or not strings(rule["3"])
        ):
            raise CheckError("Invalid shared section rule.")
    if any(not strings(names) for names in policy["frozen_signatures"].values()):
        raise CheckError("Invalid frozen signatures.")


def working_text(repo: Path, path: str) -> str:
    target = repo / path
    if target.is_symlink():
        raise SectionError("shared files must remain regular files")
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise SectionError("required file was deleted or is unreadable") from None


def index_text(repo: Path, path: str) -> str:
    try:
        return git(repo, "show", ":" + path).decode("utf-8").replace("\r\n", "\n")
    except (CheckError, UnicodeError):
        raise SectionError("required file was deleted from the index or is unreadable") from None


def path_matches(path: str, pattern: str) -> bool:
    """Glob by path component: * cannot cross '/', while ** can."""
    parts, patterns = path.split("/"), pattern.split("/")

    def match(pi: int, gi: int) -> bool:
        if gi == len(patterns):
            return pi == len(parts)
        if patterns[gi] == "**":
            return match(pi, gi + 1) or (pi < len(parts) and match(pi + 1, gi))
        return pi < len(parts) and fnmatchcase(parts[pi], patterns[gi]) and match(pi + 1, gi + 1)

    return match(0, 0)


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(path_matches(path, pattern) for pattern in patterns)


def mask_ranges(source: str, ranges: list[tuple[int, int, str]]) -> str:
    lines = source.splitlines(keepends=True)
    for start, end, name in sorted(ranges, reverse=True):
        lines[start:end] = [f"<owned:{name}>\n"]
    return "".join(lines)


def python_tree(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError:
        raise SectionError("Python syntax is invalid") from None


def mask_classes(source: str, names: list[str]) -> str:
    tree = python_tree(source)
    ranges = []
    for name in names:
        nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name]
        if len(nodes) != 1:
            raise SectionError("an owned config class is missing or duplicated")
        node = nodes[0]
        start = min([node.lineno, *[d.lineno for d in node.decorator_list]]) - 1
        ranges.append((start, node.end_lineno or node.lineno, name))
    return mask_ranges(source, ranges)


ENV_HEADER = re.compile(r"^# --- (.+?) -{3,}[ \t]*$")


def mask_env_blocks(source: str, names: list[str]) -> str:
    lines = source.splitlines(keepends=True)
    headers = [
        (index, match.group(1))
        for index, line in enumerate(lines)
        if (match := ENV_HEADER.fullmatch(line.rstrip("\r\n")))
    ]
    ranges = []
    for name in names:
        starts = [index for index, label in headers if label == name]
        if len(starts) != 1:
            raise SectionError("an owned env block marker is missing or duplicated")
        start = starts[0]
        end = next((index for index, _ in headers if index > start), len(lines))
        ranges.append((start + 1, end, name))
    return mask_ranges(source, ranges)


TOML_HEADER = re.compile(r"^\s*\[\[?([^\]]+)\]\]?\s*(?:#.*)?$")


def mask_extras(source: str, names: list[str]) -> str:
    try:
        document = tomllib.loads(source)
        extras = document["project"]["optional-dependencies"]
        if not all(
            isinstance(extras[name], list) and all(isinstance(item, str) for item in extras[name])
            for name in names
        ):
            raise SectionError("dependency extras must remain arrays of strings")
    except (tomllib.TOMLDecodeError, KeyError, TypeError):
        raise SectionError("TOML or owned dependency extras are invalid") from None
    lines = source.splitlines(keepends=True)
    headers = [
        (index, match.group(1))
        for index, line in enumerate(lines)
        if (match := TOML_HEADER.fullmatch(line.rstrip("\r\n")))
    ]
    starts = [index for index, name in headers if name == "project.optional-dependencies"]
    if len(starts) != 1:
        raise SectionError("the optional-dependencies section must remain present")
    section_start = starts[0] + 1
    section_end = next((index for index, _ in headers if index >= section_start), len(lines))
    ranges = []
    for name in names:
        key = re.compile(
            r"^\s*(?:"
            + re.escape(name)
            + r"|'"
            + re.escape(name)
            + r"'|\""
            + re.escape(name)
            + r"\")\s*="
        )
        assignments = [
            index for index in range(section_start, section_end) if key.match(lines[index])
        ]
        if len(assignments) != 1:
            raise SectionError("an owned dependency extra is missing or duplicated")
        start = assignments[0]
        for end in range(start + 1, section_end + 1):
            try:
                value = tomllib.loads("".join(lines[start:end]))
            except tomllib.TOMLDecodeError:
                continue
            if list(value) == [name] and isinstance(value[name], list):
                ranges.append((start, end, name))
                break
        else:
            raise SectionError("an owned dependency extra could not be isolated")
    return mask_ranges(source, ranges)


MASKERS = {
    "python_classes": mask_classes,
    "env_blocks": mask_env_blocks,
    "toml_extras": mask_extras,
}


def signatures(source: str, names: list[str]) -> list[tuple[str, str, str | None]]:
    tree = python_tree(source)
    result = []
    for name in names:
        nodes = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        ]
        if len(nodes) != 1:
            raise SectionError("a frozen factory signature is missing or duplicated")
        node = nodes[0]
        result.append(
            (
                type(node).__name__,
                ast.dump(node.args),
                ast.dump(node.returns) if node.returns else None,
            )
        )
    return result


def violations(
    repo: Path, commit: str, phase: str, policy: dict, *, head: str | None = None
) -> tuple[list[str], list[str]]:
    validate_policy(policy)
    raw = git(
        repo, "diff", "--name-only", "--no-renames", "-z", commit, *([head] if head else []), "--"
    )
    staged = (
        b""
        if head
        else git(repo, "diff", "--cached", "--name-only", "--no-renames", "-z", commit, "--")
    )
    indexed = {path.decode("utf-8") for path in staged.split(b"\0") if path}
    paths = sorted({path.decode("utf-8") for path in raw.split(b"\0") if path} | indexed)
    untracked = b"" if head else git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    paths = sorted(
        set(paths)
        | {
            path
            for item in untracked.split(b"\0")
            if item
            and not matches_any(path := item.decode("utf-8"), policy.get("untracked_artifacts", []))
        }
    )
    rules = policy["phases"][phase]
    committed = {
        p.decode()
        for p in git(
            repo, "diff", "--name-only", "--no-renames", "-z", commit, head or "HEAD", "--"
        ).split(b"\0")
        if p
    }
    paths = [
        p
        for p in paths
        if not (
            not head and p in policy["local_overrides"] and p not in committed and p not in indexed
        )
    ]
    errors = []
    for path in paths:
        reason = None
        if matches_any(path, policy["frozen"]):
            reason = "frozen; use an integrator compat change"
        elif matches_any(path, rules["exclude"]):
            reason = "owned by the other phase"
        elif path in policy["shared_sections"]:
            rule = policy["shared_sections"][path]
            try:
                before = baseline_text(repo, commit, path)
                versions = [baseline_text(repo, head, path) if head else working_text(repo, path)]
                if path in indexed:
                    versions.append(index_text(repo, path))
                masker = MASKERS[rule["kind"]]
                if any(
                    masker(before, rule[phase]) != masker(after, rule[phase]) for after in versions
                ):
                    reason = "changes extend outside the phase-owned section"
            except SectionError as error:
                reason = str(error)
        elif not matches_any(path, [*rules["allow"], *policy["generated"]]):
            reason = "outside this phase's ownership; ask the integrator"
        if reason is None and path in policy["frozen_signatures"]:
            try:
                before = baseline_text(repo, commit, path)
                versions = [baseline_text(repo, head, path) if head else working_text(repo, path)]
                if path in indexed:
                    versions.append(index_text(repo, path))
                names = policy["frozen_signatures"][path]
                if any(signatures(before, names) != signatures(after, names) for after in versions):
                    reason = "factory signature is frozen; use an integrator compat change"
            except SectionError as error:
                reason = str(error)
        if reason:
            errors.append(f"{json.dumps(path, ensure_ascii=False)}: {reason}")
    return paths, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=["2", "3"])
    parser.add_argument("--base")
    parser.add_argument("--head", help="Check this committed revision only (CI)")
    parser.add_argument(
        "--repo", type=Path, default=ROOT, help="Git repository (defaults to this checkout)"
    )
    args = parser.parse_args(argv)
    try:
        repo = args.repo.resolve()
        base = args.base or resolve_base(repo, args.head or "HEAD")
        commit = (
            git(repo, "rev-parse", "--verify", "--end-of-options", base + "^{commit}")
            .decode()
            .strip()
        )
        assert_base_ancestor(repo, commit, args.head or "HEAD")
        # A feature branch must not be able to relax the policy it is checked against.
        policy = json.loads(baseline_text(repo, commit, POLICY))
        validate_policy(policy)
        paths, errors = violations(repo, commit, args.phase, policy, head=args.head)
    except (CheckError, OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        message = (
            str(error)
            if isinstance(error, CheckError)
            else "Invalid ownership policy or repository input."
        )
        print("Ownership check unavailable: " + message, file=sys.stderr)
        return 2
    if errors:
        print(f"Phase {args.phase} ownership violations ({len(errors)}):")
        for error in errors:
            print("  " + error)
        return 1
    print(f"Phase {args.phase} ownership PASS: {len(paths)} changed path(s) against {commit[:12]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
