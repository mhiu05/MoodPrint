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
DEFAULT_BASE = "baseline/phase-1-verified"


class CheckError(Exception):
    """A prerequisite is missing, without exposing file contents or Git stderr."""


class SectionError(Exception):
    """An owned section is missing, ambiguous or invalid."""


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if result.returncode:
        raise CheckError("Git check failed; verify the repository and baseline reference.")
    return result.stdout


def baseline_text(repo: Path, commit: str, path: str) -> str:
    try:
        return git(repo, "show", f"{commit}:{path}").decode("utf-8").replace("\r\n", "\n")
    except (CheckError, UnicodeError):
        raise CheckError(f"Baseline is missing a readable required file: {path}") from None


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


def violations(repo: Path, commit: str, phase: str, policy: dict) -> tuple[list[str], list[str]]:
    raw = git(repo, "diff", "--name-only", "--no-renames", "-z", commit, "--")
    staged = git(repo, "diff", "--cached", "--name-only", "--no-renames", "-z", commit, "--")
    indexed = {path.decode("utf-8") for path in staged.split(b"\0") if path}
    paths = sorted({path.decode("utf-8") for path in raw.split(b"\0") if path} | indexed)
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
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
                versions = [working_text(repo, path)]
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
                versions = [working_text(repo, path)]
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
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument(
        "--repo", type=Path, default=ROOT, help="Git repository (defaults to this checkout)"
    )
    args = parser.parse_args(argv)
    try:
        repo = args.repo.resolve()
        commit = (
            git(repo, "rev-parse", "--verify", "--end-of-options", args.base + "^{commit}")
            .decode()
            .strip()
        )
        # A feature branch must not be able to relax the policy it is checked against.
        policy = json.loads(baseline_text(repo, commit, POLICY))
        if policy["version"] != 1:
            raise CheckError("Unsupported ownership policy version in baseline.")
        paths, errors = violations(repo, commit, args.phase, policy)
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
