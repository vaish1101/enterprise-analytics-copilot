from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import hashlib
import secrets
import time


class SlidingWindowLimiter:
    def __init__(self, requests_per_minute: int):
        self.limit = requests_per_minute
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._salt = secrets.token_bytes(32)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        key = hashlib.blake2b(key.encode(), key=self._salt, digest_size=16).hexdigest()
        with self._lock:
            # Expire inactive buckets: no persistent addresses or identity tracking.
            for stale in tuple(self._events):
                if not self._events[stale] or self._events[stale][-1] <= now - 60:
                    del self._events[stale]
            if key not in self._events and len(self._events) >= 10000:
                return False  # bounded memory, fail closed under address churn
            events = self._events[key]
            while events and events[0] <= now - 60:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True
