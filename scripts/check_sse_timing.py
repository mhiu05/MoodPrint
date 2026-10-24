"""Verify the first SSE event arrives before the second is produced."""

import sys
import time
from urllib.request import urlopen

started = time.monotonic()
with urlopen(sys.argv[1], timeout=8) as response:
    assert response.headers.get_content_type() == "text/event-stream"
    assert response.readline() == b"data: first\n"
    first_delay = time.monotonic() - started
    assert first_delay < 1.5, f"first event buffered for {first_delay:.2f}s"
    assert response.readline() == b"\n"
    assert response.readline() == b"data: second\n"
    assert response.readline() == b"\n"
print("SSE first event flushed before second event")
