"""Budget enforcement must prevent the call after either limit is reached."""

import pytest
from safevoice_agent.budget import RunToolBudget
from safevoice_agent.errors import PerToolBudgetExceeded, ToolBudgetExceeded


def test_per_tool_limit_does_not_consume_another_call() -> None:
    budget = RunToolBudget(max_calls=6)
    budget.consume("clock", 1)
    with pytest.raises(PerToolBudgetExceeded):
        budget.consume("clock", 1)
    assert budget.total_calls == 1


def test_run_budget_exceeded() -> None:
    budget = RunToolBudget(max_calls=2)
    budget.consume("clock", 2)
    budget.consume("read", 2)
    with pytest.raises(ToolBudgetExceeded):
        budget.consume("other", 2)
    assert budget.total_calls == 2


def test_budget_survives_approval_checkpoint() -> None:
    budget = RunToolBudget(max_calls=3)
    budget.consume("clock", 1)
    restored = RunToolBudget.from_snapshot(budget.snapshot())
    assert restored.total_calls == 1
    with pytest.raises(PerToolBudgetExceeded):
        restored.consume("clock", 1)
