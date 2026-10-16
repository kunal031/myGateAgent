"""Create the first account and give it the existing study history.

Every attempt, card view, concept progress row, exam session and
assistant thread predates accounts, so each has a null owner. Left that
way they would belong to nobody: the feed would show no progress, and a
second account registering later would see rows it never created.

    ./venv/bin/python -m app.cli.bootstrap_users --email you@example.com
    ./venv/bin/python -m app.cli.bootstrap_users --claim-orphans
"""

import argparse
import getpass

from sqlalchemy import text

from ..core.database import SessionLocal
from ..core.security import MIN_PASSWORD_CHARS, hash_password
from ..models.users import User, UserRole

#: Tables whose rows belong to one student.
OWNED_TABLES = (
    "attempts", "mistake_registry", "card_views", "concept_progress",
    "exam_sessions", "assistant_threads", "question_papers",
)

#: feed_cards is deliberately not in that list. A generated card is shared
#: -- it cost quota to produce and is identical for everyone -- so only the
#: hand-written ones are claimed.
HAND_WRITTEN_CARDS = (
    "UPDATE feed_cards SET user_id = :u "
    "WHERE user_id IS NULL AND source_type = 'user'"
)


def claim_orphans(db, user_id: int) -> dict[str, int]:
    """Give every ownerless row to `user_id`. Returns what moved."""
    moved: dict[str, int] = {}
    for table in OWNED_TABLES:
        result = db.execute(
            text(f"UPDATE {table} SET user_id = :u WHERE user_id IS NULL"),
            {"u": user_id},
        )
        if result.rowcount:
            moved[table] = result.rowcount
    result = db.execute(text(HAND_WRITTEN_CARDS), {"u": user_id})
    if result.rowcount:
        moved["feed_cards (hand-written)"] = result.rowcount
    db.commit()
    return moved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email")
    parser.add_argument("--password", help="prompted for if omitted")
    parser.add_argument("--name", default="")
    parser.add_argument("--claim-orphans", action="store_true",
                        help="only reassign ownerless rows to the first account")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.claim_orphans:
            first = db.query(User).order_by(User.id).first()
            if first is None:
                raise SystemExit("No accounts yet; run without --claim-orphans.")
            moved = claim_orphans(db, first.id)
            print(f"Claimed for {first.email}:")
            for table, count in moved.items():
                print(f"  {table:28} {count}")
            if not moved:
                print("  nothing was ownerless")
            return

        if not args.email:
            raise SystemExit("--email is required")

        email = args.email.lower().strip()
        if db.query(User).filter(User.email == email).first():
            raise SystemExit(f"{email} already has an account")

        password = args.password or getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_CHARS:
            raise SystemExit(
                f"Password must be at least {MIN_PASSWORD_CHARS} characters"
            )

        first = db.query(User.id).first() is None
        user = User(
            email=email,
            display_name=args.name.strip()[:120],
            password_hash=hash_password(password),
            role=UserRole.ADMIN if first else UserRole.STUDENT,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created {email} as {user.role}")

        if first:
            moved = claim_orphans(db, user.id)
            if moved:
                print("Claimed the existing study history:")
                for table, count in moved.items():
                    print(f"  {table:28} {count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
