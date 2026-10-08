"""Remove the placeholder feed cards used to exercise the masonry layout.

They carry a templated takeaway ("Core idea for ...") and exist only so the
feed has enough cards to show multi-column packing and infinite scroll
before real generation lands. Run this once real cards exist:

    ./venv/bin/python -m app.cli.clear_placeholders
"""

from ..core.database import SessionLocal
from ..models.models import FeedCard

PLACEHOLDER_MARKER = "Core idea for %"


def main() -> None:
    db = SessionLocal()
    try:
        removed = (
            db.query(FeedCard)
            .filter(FeedCard.takeaway.like(PLACEHOLDER_MARKER))
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"Removed {removed} placeholder cards; "
              f"{db.query(FeedCard).count()} remain.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
