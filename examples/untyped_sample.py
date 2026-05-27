"""Small HTTP client utility helpers.

Provides URL building, response parsing, and a simple retry helper used by
several internal scripts. Intentionally dependency-free so it can be vendored.
"""

import json
import time
import urllib.parse


def build_url(base, path, params=None):
    """Join a base URL with a path and optional query parameters."""
    if not base.endswith("/"):
        base = base + "/"
    if path.startswith("/"):
        path = path[1:]
    url = urllib.parse.urljoin(base, path)
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = url + "?" + query
    return url


def parse_response(raw):
    """Parse a raw HTTP response body into a Python object."""
    if raw is None or raw == "":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def is_retryable_status(status_code):
    """Return True if the given HTTP status should trigger a retry."""
    if status_code in (408, 429):
        return True
    return 500 <= status_code < 600


def retry_with_backoff(fn, max_attempts=3, base_delay=0.5):
    """Call fn() with exponential backoff until it succeeds or attempts run out."""
    attempt = 0
    last_error = None
    while attempt < max_attempts:
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
            attempt += 1
    raise last_error
