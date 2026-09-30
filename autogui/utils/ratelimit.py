# -*- coding: utf-8 -*-
"""Process-wide request rate gate shared by API clients.

Model services may throttle under load. A ``RateGate`` spaces
requests across ALL threads to stay under a per-minute budget, cutting the 429
rate before retry backoff even kicks in. Each client owns its own gate so their
budgets stay independent.
"""

import threading
import time
import math


class RateGate:
    """Global token gate spacing requests at most ``rate_per_min`` per minute.

    ``rate_per_min <= 0`` disables gating (``wait`` returns immediately). The
    gate is thread-safe: concurrent callers are serialized onto evenly spaced
    slots via a monotonic clock, so N threads still share one per-minute budget.
    """

    def __init__(self, rate_per_min: float):
        if not math.isfinite(rate_per_min) or rate_per_min < 0:
            raise ValueError('Request rate must be finite and nonnegative')
        self._min_interval = 60.0 / rate_per_min if rate_per_min > 0 else 0.0
        self._lock = threading.Lock()
        self._next_slot = 0.0   # monotonic timestamp the next request may start

    def wait(self) -> None:
        """Block until this thread may issue the next request."""
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_slot)
            self._next_slot = start + self._min_interval
        delay = start - time.monotonic()
        if delay > 0:
            time.sleep(delay)
