"""Find queries on owned tables that forget to filter by user.

A missed filter here does not fail loudly. It returns another student's
attempts, progress or conversations, and the only symptom is analytics
that look slightly wrong. That is exactly the kind of bug this codebase
has produced before, so it gets a check rather than a careful read.

The check is deliberately crude: it reads the source, finds every query
against a table that has a `user_id`, and reports the ones with no
`user_id` nearby. False positives are expected -- a count of all rows for
an admin view is legitimate -- so findings are reviewed, not trusted. The
point is that nothing is missed silently.

    ./venv/bin/python -m app.cli.audit_scoping
"""

import argparse
import re
from pathlib import Path

#: Models whose rows belong to one student.
OWNED_MODELS = (
    "Attempt", "CardView", "ConceptProgress", "ExamSession",
    "AssistantThread", "AssistantMessage", "MistakeRegistry",
    "QuestionPaper",
)

#: How many lines after a query to look for a user filter. A chained
#: SQLAlchemy query spans several lines; beyond this it is a new statement.
WINDOW = 6

#: Reasons a query legitimately has no user filter.
ALLOWED = (
    "user_id",          # the filter itself
    "current_user",     # dependency named in the signature
    "audit_scoping",    # this file
    "bootstrap_users",  # the backfill, which is cross-user by design
)

_QUERY = re.compile(
    r"(?:db|worker|session|self\.db)\.query\(\s*(" + "|".join(OWNED_MODELS) + r")\b"
)


def scan(path: Path) -> list[tuple[int, str, str]]:
    """Return (line number, model, source line) for unscoped queries."""
    findings = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        match = _QUERY.search(line)
        if not match:
            continue
        window = "\n".join(lines[index:index + WINDOW])
        if any(token in window for token in ALLOWED):
            continue
        findings.append((index + 1, match.group(1), line.strip()[:76]))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="app")
    args = parser.parse_args()

    root = Path(args.root)
    total = 0
    for path in sorted(root.rglob("*.py")):
        if path.name in {"audit_scoping.py", "bootstrap_users.py"}:
            continue
        findings = scan(path)
        if not findings:
            continue
        print(f"\n{path}")
        for line_no, model, source in findings:
            print(f"  {line_no:5}  {model:18} {source}")
            total += 1

    print(f"\n{total} quer{'y' if total == 1 else 'ies'} on owned tables "
          f"with no user filter nearby.")
    if total:
        print("Each is either a leak or a deliberate cross-user read. "
              "Decide which, and say so in a comment.")


if __name__ == "__main__":
    main()
