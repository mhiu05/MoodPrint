import pytest
from sqlalchemy import event

from app.ai.accounting import budget_liability
from app.infrastructure.database.models import now


@pytest.mark.postgres
async def test_global_liability_reads_all_domains_in_one_snapshot(clients):
    app, _ = clients
    queries = []

    def count(_conn, _cursor, statement, _parameters, _context, _many):
        queries.append(statement)

    engine = app.state.database.engine.sync_engine
    async with app.state.database.sessions() as db:
        event.listen(engine, "before_cursor_execute", count)
        try:
            assert await budget_liability(db, now()) == 0
        finally:
            event.remove(engine, "before_cursor_execute", count)
    assert len(queries) == 1
    # The query must still include each financial authority, even with no rows.
    assert all(table in queries[0] for table in (
        "ai_usage", "guest_budget_days", "guest_cost_reservations", "ai_search_usage"
    ))
