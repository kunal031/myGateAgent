"""A cache that is allowed to be missing.

Redis holds derived values that can always be recomputed from Postgres:
the syllabus tree, a user's analytics, a page of the feed. Nothing here
is a source of truth, which is what makes the central rule safe --

    **every failure is a miss.**

A refused connection, a timeout, a corrupt payload, a serialisation error:
all of them return None and the caller reads the database, exactly as it
did before this module existed. Redis going down makes the app slower,
never broken. The alternative -- letting a cache error reach the request
-- would mean adding a dependency that can take down a working app, which
is a bad trade for latency.

Keys are namespaced ``gateai:<version>:<kind>:<...>``. The version is
bumped when a cached shape changes, which retires every old entry at once
without a flush: a deploy that changes a response body cannot serve the
previous shape from cache to a new frontend.

Per-user values carry the user id in the key. That is not an
optimisation -- a shared key would serve one student's analytics to
another, which is the same class of bug as the feed-card leak.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: Bump to retire every existing entry, e.g. when a payload shape changes.
CACHE_VERSION = "v1"

NAMESPACE = "gateai"

_client: "redis.Redis | None" = None  # noqa: F821
#: Logged once rather than per request: a down Redis would otherwise
#: produce a line per call and bury everything else.
_warned = False
#: When to next attempt a connection after a failure. Without this, a
#: Redis that is not up yet when the API starts -- an ordinary race in
#: compose, where the api container can win -- would leave caching off
#: until someone restarted the process. redis-py reconnects by itself
#: once a client exists, so this only covers the first connection.
_retry_after = 0.0
RETRY_SECONDS = 30.0


def _settings_url() -> str:
    from .config import settings

    return settings.REDIS_URL.strip()


def get_client():
    """The shared client, or None when caching is off or unreachable.

    Created lazily so importing this module never opens a socket, which
    keeps it usable from CLI commands and tests that have no Redis.
    """
    global _client, _warned, _retry_after

    if _client is not None:
        return _client

    # Back off between attempts so a request does not pay the connect
    # timeout every time while Redis is down.
    now = time.monotonic()
    if now < _retry_after:
        return None
    _retry_after = now + RETRY_SECONDS

    url = _settings_url()
    if not url:
        logger.info("REDIS_URL is empty; caching is disabled")
        return None

    try:
        import redis

        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            # A cache must never be the reason a request is slow. If Redis
            # cannot answer in well under the time the database would
            # take, giving up and reading Postgres is strictly better.
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
            # Without this a dropped connection surfaces as an error on
            # the next call rather than being reconnected underneath.
            retry_on_timeout=False,
            health_check_interval=30,
        )
        client.ping()
        _client = client
        logger.info("cache: connected to Redis")
    except Exception as exc:  # noqa: BLE001 - any failure means "no cache"
        if not _warned:
            logger.warning("cache: Redis unavailable (%s); running without it", exc)
            _warned = True
        _client = None

    return _client


def reset_client() -> None:
    """Forget the cached handle. For tests, and after a config change."""
    global _client, _warned, _retry_after
    _client = None
    _warned = False
    _retry_after = 0.0


def key(kind: str, *parts: Any) -> str:
    """Build a namespaced key: gateai:v1:feed:7:30:0."""
    tail = ":".join(str(p) for p in parts)
    return f"{NAMESPACE}:{CACHE_VERSION}:{kind}" + (f":{tail}" if tail else "")


def get(name: str) -> Any | None:
    """The decoded value, or None on a miss or any failure."""
    client = get_client()
    if client is None:
        return None
    try:
        raw = client.get(name)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache: get(%s) failed: %s", name, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        # A payload written by an older, incompatible version. Treat it as
        # a miss rather than raising; it will be overwritten below.
        logger.debug("cache: undecodable payload at %s", name)
        return None


def set(name: str, value: Any, *, ttl: int) -> None:
    """Store a value under a TTL. Never raises.

    A TTL is required, deliberately. Every value here is derived, so the
    question is only how stale it may be -- and an entry with no
    expiry outlives the reasoning that justified caching it.
    """
    client = get_client()
    if client is None:
        return
    try:
        client.setex(name, ttl, json.dumps(value, default=str))
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache: set(%s) failed: %s", name, exc)


def delete(*names: str) -> None:
    """Drop keys. Never raises."""
    if not names:
        return
    client = get_client()
    if client is None:
        return
    try:
        client.delete(*names)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache: delete failed: %s", exc)


def delete_prefix(prefix: str) -> int:
    """Drop every key under a prefix. Returns how many were removed.

    Uses SCAN, not KEYS: KEYS blocks the server for the whole sweep, and
    on a shared Redis that stalls every other client. Unlinks in batches
    so a large namespace does not build one enormous command.
    """
    client = get_client()
    if client is None:
        return 0
    removed = 0
    try:
        batch: list[str] = []
        for found in client.scan_iter(match=f"{prefix}*", count=500):
            batch.append(found)
            if len(batch) >= 500:
                removed += client.unlink(*batch)
                batch = []
        if batch:
            removed += client.unlink(*batch)
    except Exception as exc:  # noqa: BLE001
        logger.debug("cache: delete_prefix(%s) failed: %s", prefix, exc)
    return removed


def get_or_set(name: str, producer: Callable[[], Any], *, ttl: int) -> Any:
    """Return the cached value, or compute, store and return it.

    The producer runs on a miss and on any cache failure, so a caller
    behaves identically with Redis absent. There is no lock around it:
    two concurrent misses both compute, which for these values is far
    cheaper than the coordination needed to prevent it.
    """
    hit = get(name)
    if hit is not None:
        return hit
    value = producer()
    set(name, value, ttl=ttl)
    return value


def enabled() -> bool:
    """Whether a Redis connection is currently usable."""
    return get_client() is not None


def stats() -> dict:
    """What the cache is doing, for /api/health."""
    client = get_client()
    if client is None:
        return {"enabled": False}
    try:
        info = client.info("stats")
        memory = client.info("memory")
        hits = int(info.get("keyspace_hits", 0))
        misses = int(info.get("keyspace_misses", 0))
        total = hits + misses
        return {
            "enabled": True,
            "keys": client.dbsize(),
            "hit_rate": round(hits / total, 3) if total else None,
            "used_memory": memory.get("used_memory_human"),
        }
    except Exception:  # noqa: BLE001
        return {"enabled": False}
