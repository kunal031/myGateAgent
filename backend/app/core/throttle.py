"""Per-caller request limiting, inside the application.

Why this exists at all, given API Gateway throttles and Lambda caps
concurrency: neither of those is per-caller. The gateway's limit is for
the whole stage, so one attacker hitting the rate limit also throttles
the legitimate user -- the denial of service succeeds. Reserved
concurrency bounds the bill but not who gets served.

AWS WAF would be the right place for per-IP limiting, but it cannot be
attached to an HTTP API (v2); its supported resources are CloudFront,
REST API, ALB, AppSync, Cognito, App Runner and a few others. Fronting
the API with CloudFront to gain WAF costs roughly $6/month in web ACL
fees, which defeats the point of staying inside the free tier. So the
cheapest place that can see the caller is here.

The counter lives in Redis when configured and in memory otherwise.
In-memory is per-container and therefore leaky under Lambda concurrency
-- ten containers each allow the full budget -- but it still bounds a
single attacker by a factor of ten rather than not at all, and it costs
nothing. With Redis it is exact.

Deliberately NOT a defence against a distributed attack. A botnet with
10,000 addresses gets 10,000 separate budgets. That case is what the
gateway throttle and reserved concurrency are for: they cap the total
regardless of how many sources it comes from.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import cache
from .config import settings


@dataclass
class _MemoryBucket:
    """Fallback counter for when Redis is absent."""

    hits: dict[str, list[float]] = field(default_factory=dict)

    def count(self, key: str, window: int, now: float) -> int:
        times = [t for t in self.hits.get(key, []) if now - t < window]
        times.append(now)
        # Bounded so a long-lived container cannot grow this without
        # limit; the cap is above any legitimate burst.
        self.hits[key] = times[-1000:]
        # Opportunistic sweep: without it, keys for callers that never
        # return stay in the dict for the life of the container.
        if len(self.hits) > MAX_TRACKED_CALLERS:
            self._evict(now, window, key)
        return len(times)

    def _evict(self, now: float, window: int, keep: str) -> None:
        """Drop stale callers, and if that is not enough, the oldest.

        Dropping only the stale ones is not sufficient: a flood from
        thousands of distinct addresses within one window leaves every
        entry fresh, so nothing is evicted and the dict grows without
        bound -- the leak this method exists to prevent, under exactly
        the conditions that matter.

        Evicting a live caller resets their count, which is the right way
        to be wrong here: an attacker gets a few extra requests, and the
        gateway throttle and reserved concurrency are still underneath.
        """
        fresh = {
            k: v for k, v in self.hits.items()
            if v and now - v[-1] < window
        }
        if len(fresh) > MAX_TRACKED_CALLERS:
            # Oldest last-seen first, never the caller being served.
            ordered = sorted(fresh.items(), key=lambda kv: kv[1][-1])
            keep_n = MAX_TRACKED_CALLERS // 2
            fresh = dict(ordered[-keep_n:])
            if keep in self.hits:
                fresh[keep] = self.hits[keep]
        self.hits = fresh


#: Above any plausible number of real simultaneous users, and small
#: enough that the dict cannot become the memory problem. A flood from
#: more distinct addresses than this evicts the oldest rather than
#: growing.
MAX_TRACKED_CALLERS = 5000

_memory = _MemoryBucket()


def _redis_count(key: str, window: int) -> int | None:
    """Increment and return the count in this window, or None without Redis.

    INCR plus EXPIRE on a window-stamped key: a fixed window rather than
    a sliding one, because it costs one round trip instead of a sorted-set
    read, and the imprecision at a window boundary is irrelevant when the
    limit is "a human studying" versus "a script".
    """
    client = cache.get_client()
    if client is None:
        return None
    try:
        slot = int(time.time()) // window
        redis_key = cache.key("throttle", key, slot)
        pipe = client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window * 2)
        count, _ = pipe.execute()
        return int(count)
    except Exception:  # noqa: BLE001 - a throttle must never 500
        return None


def check(caller: str, *, limit: int, window: int) -> tuple[bool, int]:
    """Whether this caller may proceed, and how many requests they have made.

    Returns (allowed, count). Never raises: a failure in the limiter
    must not fail the request it was meant to protect, so an error
    allows the call through -- the gateway and concurrency limits are
    still underneath.
    """
    count = _redis_count(caller, window)
    if count is None:
        count = _memory.count(caller, window, time.time())
    return count <= limit, count


def client_ip(headers, fallback: str = "unknown") -> str:
    """The caller's address as API Gateway reports it.

    X-Forwarded-For is appended to by each hop, so the *first* entry is
    the original client. Taking the last would read the gateway's own
    address and give every caller the same bucket -- which looks like it
    works until one user trips the limit for everybody.

    Spoofable in general, which is why this is a cost guardrail rather
    than an authorisation control.
    """
    forwarded = headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return fallback
