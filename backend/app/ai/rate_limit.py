"""Token-bucket rate limiting with a persistent daily cap.

The Gemini free tier allows roughly 10 requests/minute and 1,500/day, and
about 500/day for Search grounding. Ingestion runs for hours across
thousands of pages, so the daily counter is kept on disk and survives
restarts: a resumed job must not silently blow through the quota.
"""

import json
import threading
import time
from datetime import date
from pathlib import Path

from ..core.config import settings


class RateLimiter:
    def __init__(self, max_rpm: int, max_per_day: int, state_name: str):
        self._min_interval = 60.0 / max(max_rpm, 1)
        self._max_per_day = max_per_day
        self._state_path = settings.DATA_DIR / f".ratelimit_{state_name}.json"
        self._lock = threading.Lock()
        self._last_call = 0.0

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
        with self._lock:
            state = self._load()
            if state["count"] >= self._max_per_day:
                raise DailyQuotaExceeded(
                    f"Daily cap of {self._max_per_day} requests reached. "
                    f"Resume after midnight, or raise GEMINI_MAX_REQUESTS_PER_DAY "
                    f"if your key is on a paid tier."
                )

            # Reserve this caller's slot and compute its wait inside the
            # lock, so the spacing is still honoured across threads.
            now = time.monotonic()
            start_at = max(now, self._last_call + self._min_interval)
            self._last_call = start_at

            state["count"] += 1
            self._save(state)

        wait = start_at - time.monotonic()
        if wait > 0:
            time.sleep(wait)


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
