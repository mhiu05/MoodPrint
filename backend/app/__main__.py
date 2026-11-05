import os

import uvicorn

from app.core import logs
from app.core.capacity import shutdown_bounds
from app.core.config import Settings

logs.configure()
grace = shutdown_bounds(Settings().ai_timeout_seconds)["server_grace"]
configured_grace = int(os.environ.get("MOODPRINT_SHUTDOWN_SECONDS", str(grace)))
if configured_grace < grace:
    raise ValueError("MOODPRINT_SHUTDOWN_SECONDS must cover group turns and cleanup")

# One process by design: temporary chats, rate limits and stream slots are in-process
# (deploy/README.md). Proxy headers are trusted only from FORWARDED_ALLOW_IPS.
uvicorn.run(
    "app.main:app",
    host=os.environ.get("MOODPRINT_HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8001")),
    workers=1,
    loop="app.core.loop:selector_factory",
    proxy_headers=True,
    timeout_graceful_shutdown=configured_grace,
    log_config=None,
)
