"""A hand-written card is private to the account that wrote it.

These cover the bug where update_card and delete_card took no user at
all: they checked only source_type == "user", so any caller could edit or
delete any student's note by guessing its id.
"""

from app.models.models import FeedCard

from .conftest import auth


def _payload(**over):
    body = {
        "subject_slug": "t-subj", "topic_slug": "t-topic",
        "title": "rewritten", "content": "rewritten body",
    }
    body.update(over)
    return body


class TestWritesRequireTheOwner:
    def test_anonymous_cannot_edit(self, client, owned_card):
        res = client.patch(f"/api/feed/{owned_card.id}", json=_payload())
        assert res.status_code == 401

    def test_anonymous_cannot_delete(self, client, owned_card):
        assert client.delete(f"/api/feed/{owned_card.id}").status_code == 401

    def test_another_user_cannot_edit(self, client, owned_card, intruder):
        res = client.patch(f"/api/feed/{owned_card.id}",
                           json=_payload(), headers=auth(intruder))
        # 404, not 403: a 403 would confirm the id exists.
        assert res.status_code == 404

    def test_another_user_cannot_delete(self, client, owned_card, intruder):
        res = client.delete(f"/api/feed/{owned_card.id}",
                            headers=auth(intruder))
        assert res.status_code == 404

    def test_a_refused_edit_leaves_the_card_alone(
        self, client, db, owned_card, intruder,
    ):
        original = owned_card.title
        client.patch(f"/api/feed/{owned_card.id}",
                     json=_payload(title="HACKED"), headers=auth(intruder))
        db.expire_all()
        assert db.get(FeedCard, owned_card.id).title == original

    def test_a_refused_delete_leaves_the_card_alone(
        self, client, db, owned_card, intruder,
    ):
        client.delete(f"/api/feed/{owned_card.id}", headers=auth(intruder))
        db.expire_all()
        assert db.get(FeedCard, owned_card.id) is not None

    def test_the_owner_can_edit(self, client, owned_card, owner):
        res = client.patch(f"/api/feed/{owned_card.id}",
                           json=_payload(title="mine, renamed"),
                           headers=auth(owner))
        assert res.status_code == 200
        assert res.json()["title"] == "mine, renamed"

    def test_the_owner_can_delete(self, client, db, owned_card, owner):
        card_id = owned_card.id
        res = client.delete(f"/api/feed/{card_id}", headers=auth(owner))
        assert res.status_code == 204
        # A fresh query, not db.get(): the identity map still holds the
        # instance this session loaded, and refreshing it raises
        # ObjectDeletedError rather than returning None.
        db.expunge_all()
        remaining = db.query(FeedCard).filter(FeedCard.id == card_id).first()
        assert remaining is None


class TestReadsRespectOwnership:
    def test_anonymous_cannot_read_metadata(self, client, owned_card):
        assert client.get(
            f"/api/feed/{owned_card.id}/metadata").status_code == 401

    def test_another_user_cannot_read_metadata(
        self, client, owned_card, intruder,
    ):
        res = client.get(f"/api/feed/{owned_card.id}/metadata",
                         headers=auth(intruder))
        assert res.status_code == 404

    def test_another_user_cannot_read_related(
        self, client, owned_card, intruder,
    ):
        res = client.get(f"/api/feed/{owned_card.id}/related",
                         headers=auth(intruder))
        assert res.status_code == 404

    def test_the_owner_can_read_metadata(self, client, owned_card, owner):
        res = client.get(f"/api/feed/{owned_card.id}/metadata",
                         headers=auth(owner))
        assert res.status_code == 200

    def test_another_user_cannot_retag(self, client, owned_card, intruder):
        res = client.put(f"/api/feed/{owned_card.id}/tags",
                         json=[{"name": "injected"}], headers=auth(intruder))
        assert res.status_code == 404
