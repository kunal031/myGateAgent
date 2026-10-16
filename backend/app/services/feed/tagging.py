"""Resolve, attach and read concept tags.

The hover query is the one that has to be fast: it runs on mouse-over, so
it is a single indexed round trip returning the card's ancestry and its
tags grouped by type. Everything else here is write-side bookkeeping.
"""

import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...models.models import FeedCard, Subject, Topic
from ...models.tags import ConceptTag, FeedCardTag, TagRole, TagType

#: Tags are short labels, and a long one is almost always a sentence that
#: belongs in the card body instead.
MAX_TAG_NAME = 120
MAX_TAGS_PER_CARD = 24


def slugify(name: str) -> str:
    """Fold a tag name to its identity.

    Case, punctuation and accents are all noise here: "Prim's Algorithm",
    "prims algorithm" and "Prims  Algorithm" are one idea, and letting them
    become three rows defeats the point of tags as a shared vocabulary.
    """
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = re.sub(r"[^a-z0-9]+", "-", folded.lower())
    return folded.strip("-")[:MAX_TAG_NAME]


def resolve_tag(
    db: Session,
    name: str,
    *,
    tag_type: str | None = None,
    subject_id: int | None = None,
) -> ConceptTag | None:
    """Find a tag by name, or create it.

    An existing tag keeps its type: the vocabulary is shared, so one card
    asserting "Graph" is a Theorem must not retype it for every other card
    that calls it a Data Structure. The first use wins, and a wrong type is
    corrected deliberately rather than by the next writer through.
    """
    slug = slugify(name)
    if not slug:
        return None

    tag = db.execute(
        select(ConceptTag).where(ConceptTag.slug == slug)
    ).scalar_one_or_none()
    if tag is not None:
        return tag

    tag = ConceptTag(
        name=name.strip()[:MAX_TAG_NAME],
        slug=slug,
        tag_type=TagType.coerce(tag_type),
        subject_id=subject_id,
        usage_count=0,
    )
    db.add(tag)
    db.flush()  # assign an id without ending the caller's transaction
    return tag


def set_card_tags(
    db: Session,
    card: FeedCard,
    tags: list[dict],
    *,
    added_by: str = "user",
) -> list[FeedCardTag]:
    """Replace a card's tags with `tags`.

    Each entry is {name, type?, role?, note?}. Replacing rather than
    appending keeps the write idempotent: the client sends the tag list it
    wants, and does not have to diff against what is already there.
    """
    existing = {link.tag_id: link for link in card.tag_links}
    seen: set[int] = set()
    result: list[FeedCardTag] = []

    for entry in tags[:MAX_TAGS_PER_CARD]:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        tag = resolve_tag(
            db, name,
            tag_type=entry.get("type"),
            subject_id=card.subject_id,
        )
        if tag is None or tag.id in seen:
            continue
        seen.add(tag.id)

        role = TagRole.coerce(entry.get("role"))
        note = (entry.get("note") or "")[:300]

        link = existing.get(tag.id)
        if link is None:
            link = FeedCardTag(
                card_id=card.id, tag_id=tag.id, role=role,
                note=note, added_by=added_by,
            )
            db.add(link)
        else:
            link.role = role
            link.note = note
        result.append(link)

    # Drop edges the caller left out.
    for tag_id, link in existing.items():
        if tag_id not in seen:
            db.delete(link)

    db.flush()
    _refresh_usage(db, seen | set(existing))
    return result


def _refresh_usage(db: Session, tag_ids: set[int]) -> None:
    """Recount usage for the tags an edit touched.

    Recounted rather than incremented: a counter that drifts is worse than
    no counter, and the set is small enough that exactness is free.
    """
    if not tag_ids:
        return
    counts = dict(
        db.execute(
            select(FeedCardTag.tag_id, func.count(FeedCardTag.id))
            .where(FeedCardTag.tag_id.in_(tag_ids))
            .group_by(FeedCardTag.tag_id)
        ).all()
    )
    for tag in db.execute(
        select(ConceptTag).where(ConceptTag.id.in_(tag_ids))
    ).scalars():
        tag.usage_count = counts.get(tag.id, 0)


def card_metadata(db: Session, card_id: int) -> dict | None:
    """Everything a hover popover needs, in one query.

    Ancestry and tags come back together because the popover shows both and
    a second round trip on mouse-over is visible. selectinload issues one
    extra statement for the tags rather than a row per tag, so the cost does
    not grow with how heavily a card is tagged.
    """
    row = db.execute(
        select(FeedCard, Subject, Topic)
        .join(Subject, FeedCard.subject_id == Subject.id)
        .join(Topic, FeedCard.topic_id == Topic.id)
        .options(selectinload(FeedCard.tag_links).selectinload(FeedCardTag.tag))
        .where(FeedCard.id == card_id)
    ).first()
    if row is None:
        return None

    card, subject, topic = row

    links = sorted(
        card.tag_links,
        key=lambda l: (TagRole.ORDER.get(l.role, 9), l.tag.name.lower()),
    )

    # Grouped by type, because that is how the popover reads: a row per
    # kind of thing, not one flat list of unrelated labels.
    grouped: dict[str, list[dict]] = {}
    for link in links:
        grouped.setdefault(link.tag.tag_type, []).append({
            "id": link.tag.id,
            "name": link.tag.name,
            "slug": link.tag.slug,
            "role": link.role,
            "note": link.note or "",
            "added_by": link.added_by,
            "usage_count": link.tag.usage_count,
        })

    return {
        "card_id": card.id,
        "title": card.title,
        # The strict tree: exactly one path per card.
        "ancestry": {
            "subject": {"id": subject.id, "name": subject.name, "slug": subject.slug},
            "chapter": {"id": topic.id, "name": topic.name, "slug": topic.slug},
            "concept_id": card.concept_id,
            "path": f"{subject.name} → {topic.name}",
        },
        "source_type": card.source_type or "knowledge_base",
        "provenance": card.provenance or "",
        # The graph: many tags, typed, crossing subjects.
        "tags": [
            {
                "type": tag_type,
                "label": TagType.LABELS.get(tag_type, "Concept"),
                "items": items,
            }
            for tag_type, items in sorted(
                grouped.items(), key=lambda kv: TagType.ALL.index(kv[0])
            )
        ],
        "tag_count": len(links),
    }


def related_cards(
    db: Session, card_id: int, *, limit: int = 8,
) -> list[dict]:
    """Other cards sharing this one's tags, most overlap first.

    This is what the graph buys over a tree: a card on Prim's reaches a card
    on Dijkstra through 'Greedy' and 'Priority Queue' without either being
    filed near the other.
    """
    mine = select(FeedCardTag.tag_id).where(FeedCardTag.card_id == card_id)
    overlap = func.count(FeedCardTag.tag_id).label("shared")

    rows = db.execute(
        select(FeedCard, Subject.name, overlap)
        .join(FeedCardTag, FeedCardTag.card_id == FeedCard.id)
        .join(Subject, FeedCard.subject_id == Subject.id)
        .where(FeedCardTag.tag_id.in_(mine), FeedCard.id != card_id)
        .group_by(FeedCard.id, Subject.name)
        .order_by(overlap.desc(), FeedCard.id)
        .limit(limit)
    ).all()

    return [
        {
            "id": card.id,
            "title": card.title,
            "subject_name": subject_name,
            "shared_tags": int(shared),
            "source_type": card.source_type or "knowledge_base",
        }
        for card, subject_name, shared in rows
    ]
