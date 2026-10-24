"""AWS Lambda entry point for background jobs.

A separate function from the API, with a long timeout. The API's ceiling
is API Gateway's 29 seconds; a paper import fetches a page, calls Gemini
several times and writes dozens of rows, which routinely exceeds that.
Lambda's own maximum is 15 minutes, which this function uses.

Invoked asynchronously by `core.background.dispatch`, never by a user.
The payload names a job from the registry rather than carrying code, so
only deliberately registered work can run here.

Failures are logged and re-raised: an async invoke that raises is retried
twice by Lambda and then sent to the dead-letter queue, which is the
behaviour wanted for a transient Gemini or database error. Jobs are
written to be safe to re-run -- the paper row records its own progress,
so a retry resumes rather than duplicating.
"""

import logging
import os

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def handler(event, context):
    """{"job": "...", "payload": {...}} -> run it."""
    # Imported here, not at module level: Lambda's init phase has a hard
    # 10-second limit, and a slow import there fails with no useful error.
    from .core.background import JOBS
    from .core.database import SessionLocal
    # Importing the API module registers every job as a side effect.
    from .api import papers  # noqa: F401

    name = event.get("job")
    payload = event.get("payload") or {}

    if name not in JOBS:
        logger.error("Unknown job %r; registered: %s", name, sorted(JOBS))
        raise KeyError(f"Unknown background job {name!r}")

    logger.info("Running job %r with %s", name, sorted(payload))
    db = SessionLocal()
    try:
        JOBS[name](db, **payload)
        logger.info("Job %r finished", name)
        return {"job": name, "status": "ok"}
    except Exception:
        logger.exception("Job %r failed", name)
        raise
    finally:
        db.close()
