import os

import uvicorn

# One process by design: temporary chats, rate limits and stream slots are in-process
# (deploy/README.md). Proxy headers are trusted only from FORWARDED_ALLOW_IPS.
uvicorn.run(
    "app.main:app",
    host=os.environ.get("MOODPRINT_HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8001")),
    workers=1,
    loop="app.core.loop:selector_factory",
    proxy_headers=True,
    timeout_graceful_shutdown=int(os.environ.get("MOODPRINT_SHUTDOWN_SECONDS", "45")),
    log_config=None,
)
