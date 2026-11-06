"""Deterministic DeepEval smoke test: no network, no LLM judge, no API keys.
Run: uv run --no-project --python 3.12 --with deepeval==4.3.1 python .claude/scripts/verification/deepeval-smoke.py
"""
import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")

import deepeval
from deepeval.metrics import ExactMatchMetric
from deepeval.test_case import LLMTestCase

case = LLMTestCase(input="2+2?", actual_output="4", expected_output="4")
metric = ExactMatchMetric()
metric.measure(case)
assert metric.score == 1.0 and metric.is_successful(), (metric.score, metric.reason)

bad = LLMTestCase(input="2+2?", actual_output="5", expected_output="4")
fail_metric = ExactMatchMetric()
fail_metric.measure(bad)
assert fail_metric.score == 0.0 and not fail_metric.is_successful()
print(f"deepeval {deepeval.__version__}: ExactMatchMetric pass-case=1.0 fail-case=0.0 OK")
