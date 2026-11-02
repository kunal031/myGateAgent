"""Test fixtures: a throwaway SQLite database per test run.

Never the real database. These tests create users, write cards and delete
them, and pointing them at Postgres would mutate 2,304 real questions.
The app resolves its DSN at import time, so the environment is set before
anything from app.* is imported -- importing first and overriding after
gives a bound engine still pointing at Postgres.
"""

from . import env_setup  # noqa: F401  (must precede every app import)

import pytest

from fastapi.testclient import TestClient  # noqa: E402

# `import app.models` would rebind the name `app` to the package and
# shadow the FastAPI instance below, so the models are registered in
# env_setup instead and never imported that way here.
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import FeedCard, Subject, Topic  # noqa: E402
from app.models.users import User, UserRole  # noqa: E402


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


def _make_user(db, email: str, role: str) -> User:
    """Get or create. The database lives for the whole session, so a
    fixture used by several tests must not insert the same email twice."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, display_name=email.split("@")[0],
                    password_hash="", role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def owner(db):
    return _make_user(db, "owner@test.invalid", UserRole.STUDENT)


@pytest.fixture
def intruder(db):
    return _make_user(db, "intruder@test.invalid", UserRole.STUDENT)


@pytest.fixture
def admin(db):
    return _make_user(db, "admin@test.invalid", UserRole.ADMIN)


def auth(user: User) -> dict:
    """Authorization header for this user."""
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture
def subject_topic(db):
    subject = db.query(Subject).filter(Subject.slug == "t-subj").first()
    if subject is None:
        subject = Subject(name="Test Subject", slug="t-subj", icon="Book",
                          description="", weightage_marks=8.0)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    topic = db.query(Topic).filter(Topic.slug == "t-topic").first()
    if topic is None:
        topic = Topic(subject_id=subject.id, name="Test Topic",
                      slug="t-topic", importance="High")
        db.add(topic)
        db.commit()
        db.refresh(topic)
    return subject, topic


@pytest.fixture
def owned_card(db, owner, subject_topic):
    """A hand-written card belonging to `owner`."""
    subject, topic = subject_topic
    card = FeedCard(
        subject_id=subject.id, topic_id=topic.id, card_type="CONCEPT",
        title="Owner's private note", content="private body",
        takeaway="t", difficulty="Medium", source_type="user",
        user_id=owner.id,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card
