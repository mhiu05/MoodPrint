import asyncio


def selector_factory() -> asyncio.AbstractEventLoop:
    """psycopg async requires SelectorEventLoop on Windows as well as POSIX."""
    return asyncio.SelectorEventLoop()
