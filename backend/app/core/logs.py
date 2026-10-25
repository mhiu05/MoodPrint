"""Content-free operational lines on stdout (09 section 12).

uvicorn runs with log_config=None so access logs (paths carry ids) stay off; without a
handler the `moodprint` logger would drop its INFO `metric=` lines.
"""

import logging
import sys

HANDLER = "moodprint-stdout"


def configure() -> None:
    logger = logging.getLogger("moodprint")
    if not any(handler.get_name() == HANDLER for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.set_name(HANDLER)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
