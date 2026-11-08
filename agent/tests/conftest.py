"""Make the standalone ``agent/evals`` harness importable as the ``evals`` package."""

import sys
from pathlib import Path

_AGENT_ROOT = str(Path(__file__).resolve().parents[1])
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)
