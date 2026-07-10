"""
rate_limit.py — Minimal in-memory login throttle.

Brute-forcing a single shared password is the obvious attack on the current
auth model, so login attempts are rate limited per client IP: after
``max_attempts`` failures inside ``window_seconds``, that IP is blocked for
``block_seconds``. A successful login clears the counter.

This is deliberately in-memory and per-process — correct for the current
single-instance deployment. A horizontally-scaled deployment would need a
shared store (e.g. Redis) so the limit is enforced across workers.

One limiter instance is created per app in ``app.main.create_app`` and stored
on ``app.state.login_limiter``; the login route reads it from there. Keeping it
on app.state (rather than a module global) means each test app — and any future
multi-app setup — gets its own isolated limiter.
"""

import threading
import time
from collections import deque


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        block_seconds: int = 300,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        # key (client IP) -> timestamps of recent failures within the window
        self._failures: dict[str, deque] = {}
        # key -> monotonic time at which the block lifts
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()
        # Last time we swept expired state, so a burst of logins doesn't sweep
        # on every call (see _maybe_prune). /auth/login is public, so without a
        # sweep, one-shot failures from churning IPs would accumulate forever.
        self._last_prune = time.monotonic()

    def seconds_until_unblocked(self, key: str) -> int:
        """
        Return 0 if ``key`` may attempt a login now, otherwise the number of
        seconds left on its block. Expired blocks are cleared as a side effect.
        """
        now = time.monotonic()
        with self._lock:
            self._maybe_prune(now)
            until = self._blocked_until.get(key)
            if until is None:
                return 0
            if now >= until:
                # Block has expired — reset this key entirely.
                self._blocked_until.pop(key, None)
                self._failures.pop(key, None)
                return 0
            return int(until - now) + 1

    def record_failure(self, key: str) -> None:
        """Record a failed attempt; start a block once the threshold is hit."""
        now = time.monotonic()
        with self._lock:
            self._maybe_prune(now)
            window = self._failures.setdefault(key, deque())
            window.append(now)
            # Drop failures that have aged out of the window.
            while window and now - window[0] > self.window_seconds:
                window.popleft()
            if len(window) >= self.max_attempts:
                self._blocked_until[key] = now + self.block_seconds
                # The block is authoritative now — drop the window entirely so
                # we don't leave an empty deque lingering for this key.
                self._failures.pop(key, None)

    def reset(self, key: str) -> None:
        """Clear all state for ``key`` — called after a successful login."""
        with self._lock:
            self._failures.pop(key, None)
            self._blocked_until.pop(key, None)

    # ── Internal eviction (callers already hold self._lock) ────────────────
    def _maybe_prune(self, now: float) -> None:
        """Sweep expired state, but at most once per window to stay cheap."""
        if now - self._last_prune >= self.window_seconds:
            self._prune(now)
            self._last_prune = now

    def _prune(self, now: float) -> None:
        """
        Remove entries that can no longer affect any decision: blocks that have
        lifted, and failure windows whose most recent attempt has aged out.
        This bounds memory to roughly the set of IPs seen in the last window.
        """
        expired_blocks = [k for k, until in self._blocked_until.items() if now >= until]
        for k in expired_blocks:
            self._blocked_until.pop(k, None)
            self._failures.pop(k, None)

        stale_failures = [
            k for k, dq in self._failures.items()
            if k not in self._blocked_until and (not dq or now - dq[-1] > self.window_seconds)
        ]
        for k in stale_failures:
            self._failures.pop(k, None)
