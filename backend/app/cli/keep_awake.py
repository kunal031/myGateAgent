"""Keep the cloud database from being powered off for inactivity.

Aiven powers off a free service that shows "no continuative activity".
A trivial query on a schedule counts as activity, which is enough to stop
an idle study database going to sleep between evenings.

**What this cannot do.** Aiven also powers off every service in a project
when the trial ends or credits run out and no payment method is on file.
That is a billing state, not an activity one, and no amount of pinging
changes it. So this keeps the service awake *while it is entitled to run*
and nothing more -- worth stating plainly, because a keep-alive that
silently fails to prevent the shutdown you were worried about is worse
than none.

The query is `SELECT 1` rather than a count: it touches no table, takes no
locks, and cannot be slowed down by how much data has accumulated.

    python -m app.cli.keep_awake              # one ping, then exit
    python -m app.cli.keep_awake --watch      # ping on a schedule
    python -m app.cli.keep_awake --watch --every 1800

Run `--watch` under launchd, cron or a container, or call the one-shot
form from an existing scheduler.
"""

import argparse
import logging
import time
from datetime import datetime

from sqlalchemy import create_engine, text

from ..core.config import settings

logger = logging.getLogger(__name__)

#: Aiven does not document the idle threshold, so this is deliberately
#: well inside any plausible one. Thirty minutes is ~48 pings a day, which
#: is nothing against the connection limit and leaves no room for a window
#: to be missed by a single failure.
DEFAULT_INTERVAL_SECONDS = 1800

#: A ping that hangs is worse than one that fails: it holds a connection
#: and delays the next attempt past the window it was meant to protect.
CONNECT_TIMEOUT_SECONDS = 20


def ping(target: str = "aiven") -> bool:
    """Touch the database once. Returns whether it answered."""
    dsn = settings._normalise_dsn(
        settings.POSTGRESQL_AIVEN_URI if target == "aiven"
        else settings.POSTGRES_URL
    )
    if not dsn:
        logger.error("No connection string configured for %r", target)
        return False

    # A fresh engine per ping, disposed afterwards: a pooled connection
    # held open for hours is exactly what a suspending service drops
    # underneath you, and the next ping would then fail on a dead socket.
    engine = create_engine(
        dsn, connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        # Expected while the service is powered off -- the hostname stops
        # resolving entirely -- so this is a warning, not an error.
        logger.warning("Ping failed: %s", str(exc)[:160])
        return False
    finally:
        engine.dispose()


def watch(target: str, interval: int) -> None:
    """Ping forever, reporting each result."""
    print(f"Pinging {target} every {interval}s. Ctrl-C to stop.")
    print("Note: this prevents an *inactivity* power-off. It cannot keep a "
          "service running past trial expiry without a payment method.\n")

    consecutive_failures = 0
    while True:
        started = time.monotonic()
        ok = ping(target)
        elapsed = time.monotonic() - started
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if ok:
            consecutive_failures = 0
            print(f"  {stamp}  awake  ({elapsed:.1f}s)")
        else:
            consecutive_failures += 1
            print(f"  {stamp}  DOWN   (failure {consecutive_failures})")
            if consecutive_failures == 3:
                print("    -> three in a row. The service is probably powered "
                      "off; pinging cannot wake it. Start it in the console.")

        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="aiven",
                        choices=["aiven", "local"])
    parser.add_argument("--watch", action="store_true",
                        help="keep pinging instead of exiting")
    parser.add_argument("--every", type=int, default=DEFAULT_INTERVAL_SECONDS,
                        help="seconds between pings when watching")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(message)s")

    if args.watch:
        try:
            watch(args.target, max(60, args.every))
        except KeyboardInterrupt:
            print("\nstopped")
        return

    ok = ping(args.target)
    print(f"{args.target}: {'awake' if ok else 'not reachable'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
