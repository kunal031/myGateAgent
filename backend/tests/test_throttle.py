"""Per-IP request limiting.

Runs without Redis: the in-memory fallback is what Lambda uses when
REDIS_URL is unset, so it is the path most likely to be in production.
"""

from app.core import throttle


class TestClientIp:
    def test_takes_the_first_hop(self):
        """X-Forwarded-For grows by appending, so the client is first.

        Taking the last entry would read the gateway's own address and
        put every caller in one bucket -- which looks like it works
        until one user throttles everybody.
        """
        assert throttle.client_ip(
            {"x-forwarded-for": "203.0.113.9, 10.0.0.1, 10.0.0.2"}
        ) == "203.0.113.9"

    def test_single_value(self):
        assert throttle.client_ip({"x-forwarded-for": "203.0.113.9"}) == "203.0.113.9"

    def test_missing_header_falls_back(self):
        assert throttle.client_ip({}) == "unknown"


class TestLimiting:
    def setup_method(self):
        # A fresh bucket per test: the module keeps state between calls.
        throttle._memory = throttle._MemoryBucket()

    def test_allows_up_to_the_limit(self):
        results = [
            throttle.check("1.1.1.1", limit=5, window=60)[0] for _ in range(5)
        ]
        assert all(results)

    def test_refuses_past_the_limit(self):
        for _ in range(5):
            throttle.check("1.1.1.1", limit=5, window=60)
        allowed, count = throttle.check("1.1.1.1", limit=5, window=60)
        assert allowed is False
        assert count == 6

    def test_callers_are_independent(self):
        """The property that makes this worth having.

        A stage-wide throttle would let one attacker deny service to
        everyone; a per-caller one does not.
        """
        for _ in range(10):
            throttle.check("attacker", limit=5, window=60)
        assert throttle.check("someone-else", limit=5, window=60)[0] is True

    def test_an_old_window_does_not_count(self):
        import time

        now = time.time()
        bucket = throttle._MemoryBucket()
        bucket.hits["1.1.1.1"] = [now - 120, now - 90]  # outside a 60s window
        assert bucket.count("1.1.1.1", 60, now) == 1

    def test_the_memory_bucket_is_bounded(self):
        """A long-lived container must not grow this without limit."""
        import time

        now = time.time()
        bucket = throttle._MemoryBucket()
        for i in range(6000):
            bucket.count(f"ip-{i}", 60, now)
        assert len(bucket.hits) <= 5001

    def test_a_broken_cache_does_not_block_the_request(self, monkeypatch):
        """A throttle must never be the reason a request fails."""

        class Exploding:
            def pipeline(self):
                raise RuntimeError("redis down")

        monkeypatch.setattr(throttle.cache, "_client", Exploding())
        # Falls through to the in-memory counter rather than raising.
        allowed, _ = throttle.check("1.1.1.1", limit=5, window=60)
        assert allowed is True
