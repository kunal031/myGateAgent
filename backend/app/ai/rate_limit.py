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
        """Block until a request may be made. Raises if the daily cap is hit."""
        with self._lock:
            state = self._load()
            if state["count"] >= self._max_per_day:
                raise DailyQuotaExceeded(
                    f"Daily cap of {self._max_per_day} requests reached. "
                    f"Resume after midnight, or raise GEMINI_MAX_REQUESTS_PER_DAY "
                    f"if your key is on a paid tier."
                )

            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

            state["count"] += 1
            self._save(state)


class DailyQuotaExceeded(RuntimeError):
    """Raised when the configured daily request cap is exhausted."""


generation_limiter = RateLimiter(
    max_rpm=settings.GEMINI_MAX_RPM,
    max_per_day=settings.GEMINI_MAX_REQUESTS_PER_DAY,
    state_name="generation",
)

search_limiter = RateLimiter(
    max_rpm=settings.GEMINI_MAX_RPM,
    max_per_day=settings.GEMINI_SEARCH_MAX_PER_DAY,
    state_name="search",
)
