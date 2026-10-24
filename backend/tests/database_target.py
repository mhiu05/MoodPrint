from sqlalchemy.engine import make_url


def require_local_test_database(raw: str):
    """Fail before connecting or resetting anything outside a disposable local DB."""
    try:
        target = make_url(raw)
    except Exception:
        raise RuntimeError("Invalid disposable PostgreSQL test target") from None
    if (
        target.drivername != "postgresql+psycopg"
        or target.host not in ("localhost", "127.0.0.1", "::1")
        or not (target.database or "").endswith("_test")
    ):
        raise RuntimeError("Tests require a local PostgreSQL database ending _test")
    return target
