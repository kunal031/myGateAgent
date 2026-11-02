"""Add `questions.exam_set` and backfill it from the source label.

GATE runs more than one session per year and the papers differ, so a
previous-year question is only fully identified by year *and* set. The
schema recorded only the year.

Some sources already carry it -- "GATE CSE 2024 SET-1" -- so those are
parsed rather than left blank. The rest stay null: inventing a set for a
paper that never recorded one would be worse than admitting it is
unknown.

Idempotent, so a partial run can be repeated.

    python -m app.cli.migrate_exam_set --dry-run
    python -m app.cli.migrate_exam_set
    python -m app.cli.migrate_exam_set --target neon
"""

import argparse
import re

from sqlalchemy import create_engine, text

from ..core.config import settings

#: "SET-1", "Set 2", "Shift 1", "Forenoon", "Afternoon". Matched on the
#: source string, which is the only place this was ever recorded.
_SET_PATTERNS = [
    (re.compile(r"\bset[\s\-_]*([0-9]+)\b", re.I), lambda m: f"Set {m.group(1)}"),
    (re.compile(r"\bshift[\s\-_]*([0-9]+)\b", re.I), lambda m: f"Shift {m.group(1)}"),
    (re.compile(r"\bforenoon\b", re.I), lambda m: "Forenoon"),
    (re.compile(r"\bafternoon\b", re.I), lambda m: "Afternoon"),
    (re.compile(r"\bsession[\s\-_]*([0-9]+)\b", re.I),
     lambda m: f"Session {m.group(1)}"),
]

DDL = [
    ("add questions.exam_set",
     "SELECT 1 FROM information_schema.columns WHERE "
     "table_name='questions' AND column_name='exam_set'",
     "ALTER TABLE questions ADD COLUMN exam_set VARCHAR(40)"),
    ("index questions.exam_set",
     "SELECT 1 FROM pg_indexes WHERE indexname='ix_questions_exam_set'",
     "CREATE INDEX ix_questions_exam_set ON questions (exam_set)"),
]


def parse_set(label: str | None) -> str | None:
    """Pull a set label out of a source string, or None."""
    if not label:
        return None
    for pattern, render in _SET_PATTERNS:
        match = pattern.search(label)
        if match:
            return render(match)
    return None


def _engine(target: str):
    dsn = settings._normalise_dsn({
        "aiven": settings.POSTGRESQL_AIVEN_URI,
        "neon": settings.NEON_DATABASE_URL,
    }.get(target, settings.POSTGRES_URL))
    if not dsn:
        raise SystemExit(f"No connection string configured for {target!r}")
    return create_engine(dsn, connect_args={"connect_timeout": 30})


def migrate(target: str = "local", *, dry_run: bool = False) -> None:
    with _engine(target).begin() as conn:
        if not dry_run:
            for label, predicate, statement in DDL:
                if conn.execute(text(predicate)).first():
                    print(f"[{target}] already done: {label}")
                else:
                    conn.execute(text(statement))
                    print(f"[{target}] applied:    {label}")

        rows = conn.execute(text(
            "SELECT id, source FROM questions WHERE is_pyq = true"
        )).all()

        found: dict[str, int] = {}
        for qid, source in rows:
            label = parse_set(source)
            if not label:
                continue
            found[label] = found.get(label, 0) + 1
            if not dry_run:
                conn.execute(
                    text("UPDATE questions SET exam_set = :s WHERE id = :i"),
                    {"s": label, "i": qid},
                )

        verb = "would set" if dry_run else "set"
        total = sum(found.values())
        print(f"\n[{target}] {verb} exam_set on {total} of {len(rows)} PYQs")
        for label, count in sorted(found.items()):
            print(f"    {label:<12} {count}")
        print(f"\n  {len(rows) - total} PYQ(s) have no set in their source "
              "and stay null -- not every paper recorded one.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="local",
                        choices=["local", "aiven", "neon"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(args.target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
