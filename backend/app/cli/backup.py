"""Dump the database to a file, and restore one back.

The corpus is expensive to rebuild -- thousands of vision OCR pages and
13k embeddings, all paid for by API quota -- and it currently exists in
exactly two places, both of which can disappear. The Aiven free tier
expires, and a local disk is a local disk. A dump on disk is the copy that
survives losing either.

    ./venv/bin/python -m app.cli.backup                     # dump local
    ./venv/bin/python -m app.cli.backup --from-aiven        # dump the cloud
    ./venv/bin/python -m app.cli.backup --list
    ./venv/bin/python -m app.cli.backup --restore <file>    # into local
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from ..core.config import settings

BACKUP_DIR = settings.DATA_DIR / "backups"

# Keep this many dumps; older ones are pruned so the directory cannot grow
# without bound. A dump is ~60 MB compressed at the current corpus size.
KEEP_BACKUPS = 7


def _psql_dsn(sqlalchemy_url: str) -> str:
    """Strip the SQLAlchemy driver so libpq tools accept the DSN.

    SQLAlchemy writes postgresql+psycopg://; pg_dump understands only
    postgresql://.
    """
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")


def _label(dsn: str) -> str:
    host = urlparse(_psql_dsn(dsn)).hostname or "local"
    return "aiven" if "aivencloud" in host else "local"


def dump(dsn: str, *, out_dir: Path = BACKUP_DIR) -> Path:
    """Write a compressed custom-format dump and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"gatemaster-{_label(dsn)}-{stamp}.dump"

    # Custom format (-Fc) is compressed and restores selectively, which
    # matters for a dump dominated by one large table.
    result = subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
         "--file", str(path), _psql_dsn(dsn)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"pg_dump failed: {result.stderr.strip()[:400]}")
    return path


def prune(out_dir: Path = BACKUP_DIR, keep: int = KEEP_BACKUPS) -> list[Path]:
    """Delete all but the newest `keep` dumps. Returns what was removed."""
    dumps = sorted(out_dir.glob("gatemaster-*.dump"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    for old in dumps[keep:]:
        old.unlink()
        removed.append(old)
    return removed


def restore(path: Path, dsn: str) -> None:
    """Restore a dump, replacing what is there.

    --clean drops each object before recreating it, so this overwrites the
    target rather than colliding with it.
    """
    if not path.exists():
        raise SystemExit(f"No such dump: {path}")
    result = subprocess.run(
        ["pg_restore", "--clean", "--if-exists", "--no-owner",
         "--no-privileges", "--dbname", _psql_dsn(dsn), str(path)],
        capture_output=True, text=True,
    )
    # pg_restore exits non-zero on harmless "does not exist" notices from
    # --clean, so only a missing-relation failure in the output is fatal.
    if result.returncode != 0 and "error" in result.stderr.lower():
        serious = [ln for ln in result.stderr.splitlines()
                   if "error" in ln.lower() and "does not exist" not in ln]
        if serious:
            raise RuntimeError("pg_restore failed:\n" + "\n".join(serious[:8]))


def _human(size: int) -> str:
    return f"{size / 1_048_576:.1f} MB"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-aiven", action="store_true",
                        help="dump the cloud copy instead of local")
    parser.add_argument("--list", action="store_true",
                        help="show existing dumps")
    parser.add_argument("--restore", metavar="FILE",
                        help="restore this dump into local Postgres")
    parser.add_argument("--keep", type=int, default=KEEP_BACKUPS)
    args = parser.parse_args()

    if args.list:
        dumps = sorted(BACKUP_DIR.glob("gatemaster-*.dump"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not dumps:
            print(f"No dumps in {BACKUP_DIR}")
            return
        for p in dumps:
            when = datetime.fromtimestamp(p.stat().st_mtime)
            print(f"  {when:%Y-%m-%d %H:%M}  {_human(p.stat().st_size):>9}  {p.name}")
        return

    local = settings._normalise_dsn(settings.POSTGRES_URL)

    if args.restore:
        if not local:
            raise SystemExit("POSTGRES_URL is not set in backend/.env")
        path = Path(args.restore)
        if not path.is_absolute():
            path = BACKUP_DIR / path
        print(f"Restoring {path.name} into local Postgres...")
        restore(path, local)
        print("Restored.")
        return

    if args.from_aiven:
        dsn = settings._normalise_dsn(settings.POSTGRESQL_AIVEN_URI)
        if not dsn:
            raise SystemExit("POSTGRESQL_AIVEN_URI is not set in backend/.env")
    else:
        dsn = local
        if not dsn:
            raise SystemExit("POSTGRES_URL is not set in backend/.env")

    print(f"Dumping {_label(dsn)}...")
    path = dump(dsn)
    print(f"  {path}  ({_human(path.stat().st_size)})")

    for old in prune(keep=args.keep):
        print(f"  pruned {old.name}")


if __name__ == "__main__":
    main()
