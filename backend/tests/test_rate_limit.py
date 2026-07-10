"""
Tests for LoginRateLimiter — behaviour and, importantly, memory eviction.

/auth/login is public and keyed by client IP, so the limiter must not
accumulate state for IPs that never come back. These tests exercise the prune
logic directly (manipulating the internal timestamps) rather than sleeping.
"""

import time

from app.core.rate_limit import LoginRateLimiter


def test_blocks_after_threshold_and_reset_clears():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=300, block_seconds=300)
    assert rl.seconds_until_unblocked("ip") == 0
    rl.record_failure("ip")
    rl.record_failure("ip")
    assert rl.seconds_until_unblocked("ip") == 0     # still under threshold
    rl.record_failure("ip")                          # third failure trips it
    assert rl.seconds_until_unblocked("ip") > 0      # now blocked
    rl.reset("ip")
    assert rl.seconds_until_unblocked("ip") == 0     # reset clears the block


def test_block_does_not_leave_an_empty_failure_deque():
    # A tripped block should drop the failure window, not leave an empty deque.
    rl = LoginRateLimiter(max_attempts=2, window_seconds=300, block_seconds=300)
    rl.record_failure("ip")
    rl.record_failure("ip")
    assert "ip" in rl._blocked_until
    assert "ip" not in rl._failures


def test_prune_evicts_expired_blocks():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=300, block_seconds=1)
    rl.record_failure("ip")
    rl.record_failure("ip")               # blocks "ip"
    assert "ip" in rl._blocked_until
    # Simulate the block having lifted, then prune.
    rl._blocked_until["ip"] = time.monotonic() - 1
    rl._prune(time.monotonic())
    assert "ip" not in rl._blocked_until
    assert "ip" not in rl._failures


def test_prune_evicts_stale_failure_windows():
    # An IP that fails a few times (below threshold) and never returns must not
    # leave a permanent entry — this is the unbounded-growth bug being fixed.
    rl = LoginRateLimiter(max_attempts=5, window_seconds=1)
    rl.record_failure("ip")
    assert "ip" in rl._failures
    # Age its most recent attempt out of the window, then prune.
    rl._failures["ip"][-1] = time.monotonic() - 10
    rl._prune(time.monotonic())
    assert "ip" not in rl._failures


def test_prune_keeps_live_state():
    # Recent, still-relevant state must survive a prune.
    rl = LoginRateLimiter(max_attempts=5, window_seconds=300)
    rl.record_failure("live")
    rl._prune(time.monotonic())
    assert "live" in rl._failures
