import time


class TTLCache:
    """Tiny in-memory cache. Good enough for a single-process demo deployment;
    swap for Redis if you ever need multi-worker consistency."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: object):
        self._store[key] = (time.time() + self.ttl_seconds, value)

    def clear(self):
        self._store.clear()


# Shared caches used across the app.
# Long TTL for search/signals since underlying data only changes on re-ingestion,
# not on every request — this is what keeps the demo queries snappy and stable.
search_cache = TTLCache(ttl_seconds=3600)
signals_cache = TTLCache(ttl_seconds=3600)
