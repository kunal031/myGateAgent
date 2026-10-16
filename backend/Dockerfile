# Two stages: wheels are built where the compilers live, and the runtime
# image carries neither them nor the build cache. psycopg and pymupdf both
# need a toolchain to install and none to run.
FROM python:3.11-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim AS runtime

# PYTHONUNBUFFERED so logs reach docker logs as they happen. Three long
# runs were diagnosed late because buffered output made a wedged process
# look identical to a quiet one.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 curl \
 && rm -rf /var/lib/apt/lists/*

# Not root: a container that only needs to read its own code should not be
# able to write it.
RUN useradd --create-home --uid 10001 app

WORKDIR /app

COPY --from=build /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels

COPY --chown=app:app app ./app

# Written to at runtime: the OCR cache and rate-limit state. Declared so a
# volume can be mounted over it, since these must be shared once more than
# one container runs.
RUN mkdir -p /app/data && chown app:app /app/data
VOLUME ["/app/data"]

USER app
EXPOSE 8000

# Hits the app rather than the port, so a process that is listening but
# broken is still reported unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
