"""In-process counters scoped to exactly one agent run."""

from dataclasses import dataclass, field
from typing import Any, cast

from moodprint_agent.errors import PerToolBudgetExceeded, ToolBudgetExceeded


@dataclass(slots=True)
class RunToolBudget:
    max_calls: int = 6
    _counts: dict[str, int] = field(default_factory=dict[str, int], init=False, repr=False)
    _total_calls: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.max_calls < 1:
            raise ValueError("max_calls must be positive")

    @property
    def total_calls(self) -> int:
        return self._total_calls

    def consume(self, tool_name: str, max_calls_per_run: int) -> None:
        if self._total_calls >= self.max_calls:
            raise ToolBudgetExceeded
        count = self._counts.get(tool_name, 0)
        if count >= max_calls_per_run:
            raise PerToolBudgetExceeded
        self._counts[tool_name] = count + 1
        self._total_calls += 1

    def snapshot(self) -> dict[str, Any]:
        return {"max_calls": self.max_calls, "counts": dict(self._counts)}

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "RunToolBudget":
        max_calls, counts = data.get("max_calls"), data.get("counts")
        if not isinstance(max_calls, int) or not isinstance(counts, dict):
            raise ValueError("invalid budget checkpoint")
        budget = cls(max_calls=max_calls)
        for name, count in cast(dict[str, Any], counts).items():
            if not isinstance(count, int) or count < 0:
                raise ValueError("invalid budget checkpoint")
            budget._counts[name] = count
        budget._total_calls = sum(budget._counts.values())
        if budget._total_calls > budget.max_calls:
            raise ValueError("invalid budget checkpoint")
        return budget
