import os

import uvicorn

uvicorn.run(
    "app.main:app",
    host=os.environ.get("MOODPRINT_HOST", "127.0.0.1"),
    port=8001,
    loop="app.core.loop:selector_factory",
    log_config=None,
)
