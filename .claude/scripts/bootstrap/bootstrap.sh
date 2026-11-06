#!/usr/bin/env bash
# Restores the Claude Code toolkit on macOS/Linux/Git Bash. Run from the project root:
#   bash .claude/scripts/bootstrap/bootstrap.sh [--check]
command -v node >/dev/null || { echo "Node.js >= 22.22 is required." >&2; exit 1; }
exec node .claude/scripts/bootstrap/bootstrap.mjs "$@"
