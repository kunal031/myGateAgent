"""Token-bucket rate limiting with a persistent daily cap.

The Gemini free tier allows roughly 10 requests/minute and 1,500/day, and
about 500/day for Search grounding. Ingestion runs for hours across
thousands of pages, so the daily counter survives restarts: a resumed job
must not silently blow through the quota.

The counter lives in Redis when it is configured, and in a JSON file
otherwise. That choice is what decides whether this process can be
replicated. A file counter is per-container, so two API instances each
believe they own the whole daily budget and together spend twice it --
the quota is enforced by Google, so the symptom is not a clean refusal
but 429s partway through a long ingest. Redis makes INCR atomic across
every instance, which is the one thing a file cannot do.

The per-minute spacing stays process-local on purpose. It paces calls so
a burst does not trip a rate limit, and a few extra calls per minute
spread across instances is harmless, whereas coordinating every call
through Redis would put a network round trip in front of each one.
"""

import json
import threading
import time
from datetime import date
from pathlib import Path

from ..core import cache
from ..core.config import settings


class RateLimiter:
    def __init__(self, max_rpm: int, max_per_day: int, state_name: str):
        self._min_interval = 60.0 / max(max_rpm, 1)
        self._max_per_day = max_per_day
        self._name = state_name
        self._state_path = settings.DATA_DIR / f".ratelimit_{state_name}.json"
        self._lock = threading.Lock()
        self._last_call = 0.0

    # ---- shared counter (Redis) ----

    def _redis_key(self) -> str:
        """One key per budget per day, so it expires on its own."""
        return cache.key("quota", self._name, date.today().isoformat())

    def _claim_shared(self) -> int | None:
        """Atomically take one slot. Returns the new count, or None.

        None means Redis is unavailable and the caller should fall back to
        the file counter. INCR is the whole point: read-then-write would
        let two instances claim the same slot, which is exactly the race
        a shared counter exists to prevent.
        """
        client = cache.get_client()
        if client is None:
            return None
        try:
            key = self._redis_key()
            pipe = client.pipeline()
            pipe.incr(key)
            # Set the expiry every time rather than only on creation: a
            # key that somehow lost its TTL would otherwise pin the
            # counter at its cap forever. Two days, so a long-running
            # job that spans midnight still sees yesterday's key vanish
            # on schedule.
            pipe.expire(key, 172_800)
            count, _ = pipe.execute()
            return int(count)
        except Exception:  # noqa: BLE001 - fall back to the file
            return None


    def _load(self) -> dict:
        today = date.today().isoformat()
        try:
            state = json.loads(self._state_path.read_text())
            if state.get("date") == today:
                return state
        except (OSError, ValueError):
            pass
        return {"date": today, "count": 0}

    def _save(self, state: dict) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(state))
        except OSError:
            pass  # never fail a job over bookkeeping

    def remaining_today(self) -> int:
        client = cache.get_client()
        if client is not None:
            try:
                used = client.get(self._redis_key())
                return max(0, self._max_per_day - int(used or 0))
            except Exception:  # noqa: BLE001
                pass
        return max(0, self._max_per_day - self._load()["count"])

    def acquire(self) -> None:
        """Block until a request may be made. Raises if the daily cap is hit.

        The lock is held only to claim a slot, never across the sleep that
        paces requests. Holding it through the sleep serialised every
        caller, and worse, a caller abandoned mid-sleep -- which the call
        watchdog does by design -- would never release it and every later
        request would block forever. That deadlock stopped two ingest runs
        dead, with every thread parked in _pthread_cond_wait and no socket
        activity at all.
        """
        # The daily claim happens first and outside the lock: it is a
        # network call when Redis is in use, and holding the lock across
        # it would serialise every caller on it.
        shared = self._claim_shared()
        if shared is not None:
            # INCR returns the count after this claim, so the Nth caller
            # sees N and the budget is spent once N exceeds the cap.
            #
            # A refused claim is deliberately NOT given back. Decrementing
            # looks tidier -- the counter would then equal real usage --
            # but every refused caller decrements, so a burst of refusals
            # erases the successful claims too: 50 callers against a cap
            # of 10 left the counter at 1 and granted 11. Letting it drift
            # upward is safe, because the only thing read from it is
            # "is this over the cap", and it expires at midnight anyway.
            if shared > self._max_per_day:
                raise DailyQuotaExceeded(self._quota_message())
        else:
            with self._lock:
                state = self._load()
                if state["count"] >= self._max_per_day:
                    raise DailyQuotaExceeded(self._quota_message())
                state["count"] += 1
                self._save(state)

        with self._lock:
            # Reserve this caller's slot and compute its wait inside the
            # lock, so the spacing is still honoured across threads.
            now = time.monotonic()
            start_at = max(now, self._last_call + self._min_interval)
            self._last_call = start_at

        wait = start_at - time.monotonic()
        if wait > 0:
            time.sleep(wait)


    def _quota_message(self) -> str:
        return (
            f"Daily cap of {self._max_per_day} requests reached. "
            f"Resume after midnight, or raise GEMINI_MAX_REQUESTS_PER_DAY "
            f"if your key is on a paid tier."
        )


class DailyQuotaExceeded(RuntimeError):
    """Raised when the configured daily request cap is exhausted."""


# Separate counters so one workload cannot exhaust another. Ingestion is a
# multi-hour batch; generation is what the student actually sees. Sharing a
# budget meant a vision run could leave nothing for cards.
generation_limiter = RateLimiter(
    max_rpm=settings.GEMINI_MAX_RPM,
    max_per_day=settings.GEMINI_GENERATE_MAX_PER_DAY,
    state_name="generation",
)

ingest_limiter = RateLimiter(
    max_rpm=settings.GEMINI_MAX_RPM,
    max_per_day=settings.GEMINI_INGEST_MAX_PER_DAY,
    state_name="ingest",
)

search_limiter = RateLimiter(
    max_rpm=settings.GEMINI_MAX_RPM,
    max_per_day=settings.GEMINI_SEARCH_MAX_PER_DAY,
    state_name="search",
)

# The student waiting on an answer must never queue behind a batch run.
# Card generation and the assistant shared generation_limiter, so an Explain
# issued while generate_all was working took 41s instead of 10 -- the extra
# time was spent entirely in the token bucket, not in the model.
interactive_limiter = RateLimiter(
    max_rpm=settings.GEMINI_MAX_RPM,
    max_per_day=settings.GEMINI_INTERACTIVE_MAX_PER_DAY,
    state_name="interactive",
)
