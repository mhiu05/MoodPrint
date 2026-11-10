"""Conservative static SQL scope guard for Phase 2/3 migration files.

This is deliberately a supported subset, not a PostgreSQL parser or a proof of
authorization. Unknown statements, procedural bodies, dynamic SQL, search_path
changes and ambiguous unqualified targets fail closed. SQL function bodies are
inspected, never discarded as literals. pgTAP/integration remain mandatory for
actual grants, policy predicates, runtime function behavior and catalog state.
Unsupported valid SQL requires integrator review and an explicit checker change.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def tokens(sql: str) -> list[tuple[str, str]]:
    result = []
    i = 0
    while i < len(sql):
        if sql[i].isspace():
            i += 1
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            i = len(sql) if end < 0 else end + 1
        elif sql.startswith("/*", i):
            depth = 1
            i += 2
            while i < len(sql) and depth:
                if sql.startswith("/*", i):
                    depth += 1
                    i += 2
                elif sql.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ValueError("Unterminated SQL comment")
        elif sql[i] in "'\"":
            quote = sql[i]
            i += 1
            value = ""
            while i < len(sql):
                if sql[i] == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote:
                        value += quote
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    if sql[i] == "\\":
                        raise ValueError("Backslash escapes require explicit review")
                    value += sql[i]
                    i += 1
            else:
                raise ValueError("Unterminated quoted SQL token")
            result.append(("literal" if quote == "'" else "identifier", value))
        elif sql[i] == "$":
            match = re.match(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$", sql[i:])
            if not match:
                raise ValueError("Unsupported dollar token")
            delimiter = match[0]
            end = sql.find(delimiter, i + len(delimiter))
            if end < 0:
                raise ValueError("Unterminated dollar body")
            result.append(("body", sql[i + len(delimiter) : end]))
            i = end + len(delimiter)
        elif sql[i].isalpha() or sql[i] == "_":
            match = re.match(r"[A-Za-z_][A-Za-z_0-9$]*", sql[i:])
            if not match:
                raise ValueError("Unsupported identifier")
            result.append(("word", match[0].lower()))
            i += len(match[0])
        elif sql[i] in "(),;.[]=:+-*/<>!%|&" or sql[i].isdigit():
            result.append(("symbol", sql[i]))
            i += 1
        else:
            raise ValueError("Unsupported SQL token")
    return result


def _statements(items):
    statement = []
    for token in items:
        if token == ("symbol", ";"):
            if statement:
                yield statement
            statement = []
        else:
            statement.append(token)
    if statement:
        yield statement


def _qualified(items, index):
    if (
        index + 2 >= len(items)
        or items[index][0] not in {"word", "identifier"}
        or items[index + 1] != ("symbol", ".")
        or items[index + 2][0] not in {"word", "identifier"}
    ):
        raise ValueError("SQL targets must be explicitly schema-qualified")
    return items[index][1] + "." + items[index + 2][1]


def _after(items, word):
    try:
        return items.index(("word", word)) + 1
    except ValueError:
        raise ValueError(f"Expected SQL keyword {word}") from None


def _optional(items, index, words):
    if items[index : index + len(words)] == [("word", word) for word in words]:
        return index + len(words)
    return index


def _reject_parent_attachment(items) -> None:
    """Reject CREATE TABLE forms that attach storage to an existing parent.

    INHERITS makes ordinary parent SELECT/UPDATE/DELETE include child rows and
    does not copy parent UNIQUE/FK enforcement. PARTITION OF attaches the new
    table to a parent partition tree. Both change baseline catalog semantics,
    so they stay unsupported until an integrator adds a reviewed exception.
    Detection uses statement tokens and parenthesis depth: comments, string
    literals, and a column merely named inherits are not table attachment.
    """
    depth = 0
    for index, token in enumerate(items):
        if token == ("symbol", "("):
            depth += 1
            continue
        if token == ("symbol", ")"):
            depth -= 1
            continue
        if depth != 0:
            continue
        if token == ("word", "inherits"):
            raise ValueError(
                "CREATE TABLE INHERITS changes parent semantics and requires integrator review"
            )
        if (
            token == ("word", "partition")
            and index + 1 < len(items)
            and items[index + 1] == ("word", "of")
        ):
            raise ValueError(
                "CREATE TABLE PARTITION OF changes parent semantics and requires integrator review"
            )


def _references(items, allowed):
    # Qualified references (including inside quoted identifiers) cannot cross
    # ownership boundaries. Alias-qualified columns are intentionally unsupported.
    for index in range(len(items) - 2):
        if items[index][0] in {"word", "identifier"} and items[index + 1] == ("symbol", "."):
            if items[index][1] not in allowed:
                raise ValueError("Reference outside the phase schemas")
    forbidden = {
        "do",
        "call",
        "copy",
        "truncate",
        "reset",
        "set_config",
        "dblink",
        "pg_read_file",
        "pg_read_binary_file",
        "lo_import",
        "lo_export",
        "query_to_xml",
        "regclass",
        "regproc",
        "regprocedure",
        "regnamespace",
        "regrole",
        "to_regclass",
        "to_regproc",
        "to_regprocedure",
        "to_regnamespace",
        "to_regrole",
    }
    if any(kind == "word" and value in forbidden for kind, value in items):
        raise ValueError("Unsupported or unsafe SQL operation")
    if any(token == ("word", "definer") for token in items):
        raise ValueError("SECURITY DEFINER requires integrator review")


def _query(items, allowed):
    if not items or items[0] != ("word", "select"):
        raise ValueError("Only SELECT bodies are supported in SQL functions")
    _references(items, allowed)
    forbidden = {
        "into",
        "insert",
        "update",
        "delete",
        "create",
        "alter",
        "drop",
        "grant",
        "revoke",
        "execute",
    }
    if any(kind == "word" and value in forbidden for kind, value in items):
        raise ValueError("SQL function body must be read only")
    for index, token in enumerate(items):
        if token in {("word", "from"), ("word", "join")}:
            _qualified(items, index + 1)
        if (
            token[0] in {"word", "identifier"}
            and index + 1 < len(items)
            and items[index + 1] == ("symbol", "(")
            and (index == 0 or items[index - 1] != ("symbol", "."))
        ):
            safe_calls = {
                "count",
                "sum",
                "min",
                "max",
                "avg",
                "coalesce",
                "nullif",
                "greatest",
                "least",
                "lower",
                "upper",
                "length",
                "char_length",
                "jsonb_build_object",
                "jsonb_agg",
                "array_agg",
                "round",
                "abs",
                "exists",
                "in",
                "any",
                "all",
                "cast",
            }
            if token[0] != "word" or token[1] not in safe_calls:
                raise ValueError("Unreviewed unqualified function call in SQL body")


def check_sql(sql: str, phase: str, baseline: set[str], created: set[str] | None = None) -> None:
    if phase not in {"kb", "ag"}:
        raise ValueError("Unknown migration phase")
    allowed = {"knowledge"} if phase == "kb" else {"app", "agent_store"}
    created = created if created is not None else set()
    for items in _statements(tokens(sql)):
        _references(items, allowed)
        words = [value for kind, value in items if kind == "word"]
        action = items[0][1] if items[0][0] == "word" else ""
        if items in ([("word", "begin")], [("word", "commit")]):
            continue
        target = None
        if action == "create":
            index = _optional(items, 1, ["or", "replace"])
            replacing = index != 1
            index = _optional(items, index, ["unique"])
            if index >= len(items) or items[index][0] != "word":
                raise ValueError("Unsupported CREATE statement")
            kind = items[index][1]
            index += 1
            if replacing and (phase == "ag" or kind != "function"):
                raise ValueError("Replacing existing objects requires integrator review")
            if kind == "schema" and phase == "kb":
                index = _optional(items, index, ["if", "not", "exists"])
                if len(items) != index + 1 or items[index][1] != "knowledge":
                    raise ValueError("Only CREATE SCHEMA knowledge is allowed")
                continue
            if kind == "table":
                index = _optional(items, index, ["if", "not", "exists"])
                target = _qualified(items, index)
                if phase == "ag" and target in baseline:
                    raise ValueError("Cannot recreate a baseline table")
                if "as" in words:
                    raise ValueError("CREATE TABLE AS requires review")
                _reject_parent_attachment(items)
                created.add(target)
            elif kind == "index":
                target = _qualified(items, _after(items, "on"))
                if phase == "ag" and target in baseline and "concurrently" not in words:
                    raise ValueError("Baseline indexes require CONCURRENTLY")
                if phase == "ag" and target not in baseline and target not in created:
                    raise ValueError("Index target must be a new phase table or baseline table")
            elif kind in {"policy", "trigger"}:
                target = _qualified(items, _after(items, "on"))
                if phase == "ag" and (target in baseline or target not in created):
                    raise ValueError("Policy/trigger may only modify a new phase table")
            elif kind == "function":
                target = _qualified(items, index)
                if items[_after(items, "language")] != ("word", "sql"):
                    raise ValueError("Procedural function bodies require integrator review")
                bodies = [value for token_kind, value in items if token_kind in {"body", "literal"}]
                if len(bodies) != 1:
                    raise ValueError("SQL function must have exactly one inspectable body")
                for body in _statements(tokens(bodies[0])):
                    _query(body, allowed)
                created.add(target)
            else:
                # Even IF NOT EXISTS extensions can create objects on a different
                # deployment. Only the integrator may approve extension DDL.
                raise ValueError("Unsupported CREATE object; integrator review required")
        elif action == "alter":
            if items[1:2] != [("word", "table")]:
                raise ValueError("Only scoped ALTER TABLE is supported")
            target = _qualified(items, _optional(items, 2, ["if", "exists"]))
            if phase == "ag" and (target in baseline or target not in created):
                raise ValueError("Cannot alter a baseline or unknown table")
            if any(
                word in words for word in {"rename", "set", "owner", "attach", "detach", "inherits"}
            ):
                raise ValueError("Table relocation/ownership/inheritance requires review")
        elif action == "drop":
            if len(items) < 2 or items[1][1] not in {
                "table",
                "function",
                "index",
                "policy",
                "trigger",
            }:
                raise ValueError("Unsupported DROP object")
            kind = items[1][1]
            target = _qualified(
                items,
                _after(items, "on")
                if kind in {"policy", "trigger"}
                else _optional(items, 2, ["if", "exists"]),
            )
            if phase == "ag" and (target in baseline or target not in created):
                raise ValueError("Cannot drop a baseline or unknown object")
            if "cascade" in words:
                raise ValueError("DROP CASCADE requires review")
            depth = 0
            for token in items:
                if token == ("symbol", "("):
                    depth += 1
                elif token == ("symbol", ")"):
                    depth -= 1
                elif token == ("symbol", ",") and depth == 0:
                    raise ValueError("Use separate statements for separate DROP targets")
        elif action in {"grant", "revoke"}:
            index = _after(items, "on")
            if items[index][1] == "schema":
                if items[index + 1][1] not in allowed:
                    raise ValueError("Schema grant outside phase scope")
                if phase == "ag":
                    raise ValueError("Phase 3 cannot change shared schema privileges")
            else:
                index = _optional(items, index, ["table"])
                index = _optional(items, index, ["function"])
                target = _qualified(items, index)
                if phase == "ag" and (target in baseline or target not in created):
                    raise ValueError("Cannot change baseline or unknown table privileges")
            # Multiple targets must each be qualified. Single-target statements
            # keep ownership checks unambiguous (role lists remain permitted).
            end = _after(items, "to" if action == "grant" else "from") - 1
            if ("symbol", ",") in items[index:end]:
                raise ValueError("Use separate statements for separate grant targets")
        elif action == "comment":
            index = _after(items, "on")
            if items[index][1] not in {"table", "column", "function", "index"}:
                raise ValueError("Unsupported COMMENT target")
            target = _qualified(items, index + 1)
            if phase == "ag" and (target in baseline or target not in created):
                raise ValueError("Cannot change baseline or unknown object comments")
        elif action in {"delete", "update"}:
            target = _qualified(items, 2 if action == "delete" else 1)
            depth = 0
            where = False
            for kind, value in items:
                if (kind, value) == ("symbol", "("):
                    depth += 1
                elif (kind, value) == ("symbol", ")"):
                    depth -= 1
                elif (kind, value) == ("word", "where") and depth == 0:
                    where = True
            if not where or (phase == "ag" and target not in created):
                raise ValueError("Data mutation requires a top-level WHERE and phase-owned table")
        else:
            raise ValueError("Unsupported SQL statement; integrator review required")
        if target and target.split(".")[0] not in allowed:
            raise ValueError("Object target outside phase schemas")


def check_migrations(source: Path, baseline: set[str]) -> int:
    spec = importlib.util.spec_from_file_location(
        "scope_order", Path(__file__).with_name("migration_order_check.py")
    )
    assert spec and spec.loader
    order = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(order)
    files = order.migrations(source)
    created = {"kb": set(), "ag": set()}
    count = 0
    for name, content in files:
        phase = name.split("_")[1]
        if phase in created:
            try:
                check_sql(content.decode("utf-8"), phase, baseline, created[phase])
            except (ValueError, IndexError) as error:
                raise ValueError(f"{name}: {error}") from None
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.branch == "feat/knowledge-ingestion-rag":
        parser.exit(2, "Retired branch profile\n")
    if args.branch and args.branch not in {
        "feat/knowledge-base",
        "feat/agent-companion",
        "integration/phase-2-3",
        "integration/pre-branch-readiness",
    }:
        print("Migration scope: no profile")
        return
    try:
        manifest = json.loads(
            (args.root / "docs/implementation/schema-manifest.json").read_text(encoding="utf-8")
        )
        baseline = {
            f"{schema}.{table}"
            for schema, tables in manifest["baseline_tables"].items()
            for table in tables
        }
        count = check_migrations(args.root / "supabase/migrations", baseline)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Migration scope failed: {error}\n")
    print(f"Migration scope: VERIFIED ({count} phase migrations)")


if __name__ == "__main__":
    main()
