"""Running work that outlives the request that asked for it.

A long-lived server can hand this to a thread. Lambda cannot: the
execution environment is **frozen the moment the handler returns**, so a
daemon thread stops mid-statement and may never be resumed. The import
would leave a paper row saying "parsing" forever, and nothing would
report an error -- the request already returned 200.

So the same call does one of two things depending on where it runs:

* **Locally** -- a daemon thread, as before. There is no broker to run
  for a single-user study app, and the work is recoverable from the paper
  row if the process dies.
* **On Lambda** -- an asynchronous invoke of a second function, which gets
  its own 15-minute timeout instead of the API's 29-second ceiling.

The dispatch is by name, not by passing a callable: a Lambda invoke
carries a JSON payload, and a function object cannot cross that boundary.
`JOBS` is the registry of what may be invoked, which also means an
attacker who could forge an invoke payload can only reach jobs that were
deliberately registered.
"""

import json
import logging
import os
from collections.abc import Callable

from .config import settings

logger = logging.getLogger(__name__)

#: Job name -> the function that runs it. Populated by register().
JOBS: dict[str, Callable] = {}


def register(name: str) -> Callable:
    """Mark a function as invokable as a background job."""
    def wrap(fn: Callable) -> Callable:
        JOBS[name] = fn
        return fn
    return wrap


def _run_thread(name: str, payload: dict) -> None:
    """Local path: a daemon thread with its own session."""
    import threading

    from .database import SessionLocal

    def runner() -> None:
        worker = SessionLocal()
        try:
            JOBS[name](worker, **payload)
        except Exception:
            logger.exception("Background job %r failed", name)
        finally:
            worker.close()

    threading.Thread(target=runner, daemon=True).start()


def _run_lambda(name: str, payload: dict) -> None:
    """Serverless path: asynchronously invoke the worker function.

    InvocationType="Event" returns as soon as the request is accepted, so
    the API request is not waiting on a job that may take ten minutes.
    """
    import boto3

    target = settings.WORKER_FUNCTION_NAME
    if not target:
        raise RuntimeError(
            "WORKER_FUNCTION_NAME is not set, so there is nowhere to send "
            "background work. On Lambda this must point at the worker "
            "function, or imports would be silently dropped."
        )

    client = boto3.client("lambda")
    client.invoke(
        FunctionName=target,
        InvocationType="Event",
        Payload=json.dumps({"job": name, "payload": payload}).encode(),
    )
    logger.info("Dispatched job %r to %s", name, target)


def dispatch(name: str, **payload) -> None:
    """Run a registered job, by whichever mechanism this environment has."""
    if name not in JOBS:
        raise KeyError(f"Unknown background job {name!r}")

    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        _run_lambda(name, payload)
    else:
        _run_thread(name, payload)
