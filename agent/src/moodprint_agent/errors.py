"""Content-free runtime failures safe to map to the public event contract."""


class ToolBudgetExceeded(Exception):
    """The run has reached its total tool-call allowance."""


class PerToolBudgetExceeded(Exception):
    """One tool has reached its allowance; other tools can still run."""


class InvalidApprovalState(ValueError):
    """The persisted state has no matching pending approval."""
