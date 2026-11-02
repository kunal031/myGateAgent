"""The cache must be optional, and must never leak between users.

No Redis is required to run these: the point of most of them is that the
module behaves correctly when it cannot connect, which is also how CI
runs them.
"""

from app.core import cache


class TestAbsentRedisIsHarmless:
    """With no REDIS_URL, every operation is a well-behaved no-op."""

    def setup_method(self):
        cache.reset_client()

    def test_disabled_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(cache, "_settings_url", lambda: "")
        assert cache.enabled() is False

    def test_get_returns_none(self, monkeypatch):
        monkeypatch.setattr(cache, "_settings_url", lambda: "")
        assert cache.get(cache.key("t", 1)) is None

    def test_set_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(cache, "_settings_url", lambda: "")
        cache.set(cache.key("t", 1), {"a": 1}, ttl=10)

    def test_get_or_set_still_produces(self, monkeypatch):
        monkeypatch.setattr(cache, "_settings_url", lambda: "")
        calls = []

        def produce():
            calls.append(1)
            return "from_db"

        assert cache.get_or_set(cache.key("t", 2), produce, ttl=10) == "from_db"
        # Nothing was stored, so the producer runs every time -- which is
        # exactly the pre-cache behaviour.
        assert cache.get_or_set(cache.key("t", 2), produce, ttl=10) == "from_db"
        assert len(calls) == 2

    def test_delete_and_prefix_do_not_raise(self, monkeypatch):
        monkeypatch.setattr(cache, "_settings_url", lambda: "")
        cache.delete(cache.key("t", 1))
        assert cache.delete_prefix(cache.key("t")) == 0

    def test_stats_reports_disabled(self, monkeypatch):
        monkeypatch.setattr(cache, "_settings_url", lambda: "")
        assert cache.stats() == {"enabled": False}


class TestUnreachableRedisIsHarmless:
    """A configured but dead Redis behaves the same as none at all."""

    def setup_method(self):
        cache.reset_client()

    def test_dead_port_is_a_miss_not_an_error(self, monkeypatch):
        # Port 1 is reserved and never listening.
        monkeypatch.setattr(cache, "_settings_url", lambda: "redis://127.0.0.1:1/0")
        assert cache.enabled() is False
        assert cache.get(cache.key("t", 3)) is None
        assert cache.get_or_set(cache.key("t", 3), lambda: "db", ttl=10) == "db"

    def test_a_client_that_throws_is_treated_as_a_miss(self, monkeypatch):
        """The central rule, exercised where it actually lives.

        Connecting to a dead port short-circuits in get_client(), so it
        never reaches the error handling inside get/set. This installs a
        client whose every call raises, which is what a Redis that
        accepted the connection and then failed looks like.
        """

        class Exploding:
            def get(self, *a, **k):
                raise RuntimeError("redis exploded")

            def setex(self, *a, **k):
                raise RuntimeError("redis exploded")

            def delete(self, *a, **k):
                raise RuntimeError("redis exploded")

            def scan_iter(self, *a, **k):
                raise RuntimeError("redis exploded")

        monkeypatch.setattr(cache, "_client", Exploding())

        assert cache.get(cache.key("t", 9)) is None
        cache.set(cache.key("t", 9), {"a": 1}, ttl=10)  # must not raise
        cache.delete(cache.key("t", 9))                 # must not raise
        assert cache.delete_prefix(cache.key("t")) == 0
        assert cache.get_or_set(cache.key("t", 9), lambda: "db", ttl=10) == "db"

    def test_an_undecodable_payload_is_a_miss(self, monkeypatch):
        """A value written by an older, incompatible version."""

        class Garbage:
            def get(self, *a, **k):
                return "{not json"

        monkeypatch.setattr(cache, "_client", Garbage())
        assert cache.get(cache.key("t", 10)) is None

    def test_failure_is_retried_later_not_latched_forever(self, monkeypatch):
        """A Redis that is not up yet must not disable caching for good.

        The api container can win the race against redis in compose; if
        the first failure were permanent, caching would stay off until
        someone restarted the process.
        """
        monkeypatch.setattr(cache, "_settings_url", lambda: "redis://127.0.0.1:1/0")
        assert cache.enabled() is False
        assert cache._retry_after > 0


class TestKeysAreScoped:
    def test_version_is_in_every_key(self):
        assert cache.key("stats", 1).startswith(f"gateai:{cache.CACHE_VERSION}:")

    def test_different_users_get_different_keys(self):
        """The property that stops one student's analytics reaching another."""
        assert cache.key("stats", 1, "deep") != cache.key("stats", 2, "deep")

    def test_key_parts_are_ordered(self):
        assert cache.key("feed", 7, 30, 0) == f"gateai:{cache.CACHE_VERSION}:feed:7:30:0"
