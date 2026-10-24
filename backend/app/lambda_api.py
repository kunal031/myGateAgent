"""AWS Lambda entry point for the HTTP API.

Mangum translates an API Gateway event into the ASGI call FastAPI expects,
so the same `app` serves uvicorn locally and Lambda in production. Nothing
about the routes changes.

Two things here are not boilerplate.

**`lifespan="off"`.** FastAPI's lifespan runs startup and shutdown hooks
around a long-lived server. Lambda has neither: the container is frozen
between invocations and killed without warning, so a shutdown hook may
never run and a startup hook would run again on every cold start. Leaving
it on means paying startup cost per cold start and silently skipping
cleanup. The work those hooks do -- creating tables, warming caches --
belongs in a deploy step, not in a request path.

**The import is deferred into the handler.** Module-level import of the
whole app happens during Lambda's init phase, which has a hard 10-second
limit; exceeding it fails the invocation with no useful error. Importing
inside the handler moves it into the (longer) invocation timeout, where a
slow import shows up as a slow first request instead of a mysterious
init failure. The module object is cached afterwards, so warm invocations
pay nothing.
"""

import logging
import os

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_handler = None


def _build():
    """Create the Mangum handler once per container."""
    from mangum import Mangum

    from .main import app

    return Mangum(
        app,
        lifespan="off",
        # API Gateway sends the stage as the first path segment on the
        # default execute-api domain. Stripping it keeps routes matching
        # whether the function is reached through a custom domain or not.
        api_gateway_base_path=os.environ.get("API_GATEWAY_BASE_PATH", "/"),
    )


def handler(event, context):
    """API Gateway -> FastAPI."""
    global _handler
    if _handler is None:
        _handler = _build()
    return _handler(event, context)
