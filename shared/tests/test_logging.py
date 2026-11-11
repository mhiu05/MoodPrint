import asyncio
import io
import json
import logging


def captured(message, extra=None, args=()):
    from safevoice_shared.logging import JsonFormatter, RedactingFilter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.Logger("privacy-test")
    logger.addHandler(handler)
    logger.info(message, *args, extra=extra)
    return json.loads(stream.getvalue())


def test_redacts_authorization_header():
    result = captured(
        {
            "authorization": "Bearer synthetic-private",
            "nested": {"content": "private-story"},
            "safe": "ok",
        }
    )
    assert "synthetic-private" not in str(result)
    assert "private-story" not in str(result)
    assert "ok" in str(result)


def test_redacts_jwt_inside_message():
    result = captured(
        "credential=%s key=sk-synthetic-private secret=sb_secret_private",
        args=("eyJhbGciOiJ0ZXN0In0.eyJzdWIiOiJ0ZXN0In0.synthetic",),
    )
    assert "eyJ" not in str(result)
    assert "sk-synthetic" not in str(result)
    assert "sb_secret_" not in str(result)


async def test_request_id_propagates():
    from safevoice_shared.logging import request_id_context

    with request_id_context("request-one"):
        await asyncio.sleep(0)
        assert captured("safe")["request_id"] == "request-one"
    assert captured("safe")["request_id"] is None


def test_exception_details_are_never_logged():
    from safevoice_shared.logging import JsonFormatter, RedactingFilter

    record = logging.LogRecord("privacy", logging.ERROR, "", 1, "operation failed", (), None)
    try:
        raise RuntimeError("private story and database credentials")
    except RuntimeError:
        import sys

        record.exc_info = sys.exc_info()
    RedactingFilter().filter(record)
    result = JsonFormatter().format(record)
    assert "private story" not in result
    assert "RuntimeError" in result


def test_server_owned_logger_handlers_cannot_bypass_privacy_filter(capsys):
    from safevoice_shared.logging import configure_logging

    logger = logging.getLogger("uvicorn")
    previous_handlers, previous_propagate = logger.handlers[:], logger.propagate
    logger.handlers = [logging.StreamHandler()]
    logger.propagate = False
    try:
        configure_logging(production=True)
        try:
            raise RuntimeError("private-exception-canary")
        except RuntimeError:
            logger.exception("request_failed")
        output = capsys.readouterr().err
        assert "request_failed" in output
        assert "private-exception-canary" not in output
    finally:
        logger.handlers, logger.propagate = previous_handlers, previous_propagate
