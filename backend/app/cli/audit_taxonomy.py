"""Report suspected duplicate and misfiled taxonomy rows.

Reports only. Nothing is merged, moved or deleted, because an automatic
merge here is unsafe in a way that is hard to notice later: concepts carry
feed cards and topics carry questions, so merging the wrong pair takes
content with it, and the result still renders perfectly -- it is simply
attached to the wrong idea.

Three checks:

* **Duplicate concepts within a topic** -- near-identical names, compared
  after normalising case, punctuation and a few plural/synonym variants.
* **Cross-subject leakage** -- a concept whose name matches another
  subject's vocabulary far better than its own. This is what catches
  "Minimum Spanning Tree Properties" sitting under Operating Systems.
* **Thin or empty topics** -- a topic with no questions or almost no
  cards, which usually means content landed somewhere else.

    python -m app.cli.audit_taxonomy
    python -m app.cli.audit_taxonomy --subject operating-systems
"""

import argparse
import re
from collections import defaultdict

from sqlalchemy import text

from ..core.database import SessionLocal

#: Vocabulary that strongly implies a subject. Used only to flag a possible
#: misfiling for review -- never to move anything. Deliberately narrow: a
#: word appears here only if it would be surprising in another subject.
SUBJECT_VOCAB: dict[str, set[str]] = {
    "algorithms": {
        "spanning tree", "dijkstra", "bellman", "floyd", "knapsack",
        "huffman", "greedy", "divide and conquer", "master theorem",
        "asymptotic", "recurrence", "graph traversal", "bfs", "dfs",
        "dynamic programming", "sorting", "quicksort", "mergesort",
    },
    "operating-systems": {
        "semaphore", "mutex", "deadlock", "scheduling", "page replacement",
        "paging", "tlb", "context switch", "process control block",
        "thread", "banker's", "critical section", "peterson",
    },
    "databases": {
        "normalization", "normal form", "functional dependency", "sql",
        "relational algebra", "transaction", "acid", "serializability",
        "b+ tree", "b-tree index", "tuple",
    },
    "computer-networks": {
        "subnet", "cidr", "tcp", "udp", "ip address", "routing",
        "sliding window", "congestion", "dns", "rsa encryption", "checksum",
    },
    "digital-logic": {
        "k-map", "karnaugh", "flip-flop", "multiplexer", "decoder",
        "boolean", "logic gate", "counter", "ieee 754", "two's complement",
    },
    "theory-of-computation": {
        "turing", "pumping lemma", "regular expression", "dfa", "nfa",
        "context-free", "pushdown", "decidab*", "undecidab*", "halting",
    },
    "compiler-design": {
        "parsing", "ll(1)", "lr(", "slr", "lalr", "first set", "follow set",
        "syntax directed", "basic block", "three address",
    },
    "computer-organization-architecture": {
        "pipelin*", "addressing mode", "cache", "hazard", "instruction cycle",
        "dma", "interrupt", "write-back", "write-through",
    },
}

#: Normalisations applied before comparing two names, so that
#: "Unsigned and Signed Integer Representations" and "Unsigned versus
#: Signed Integer Representation" collapse to the same key.
_FILLER = re.compile(
    r"\b(and|versus|vs|the|of|in|a|an|for|to|its|with|their)\b"
)


def _matches(term: str, haystack: str) -> bool:
    """Whole-word match, so a term cannot fire inside another word.

    Substring matching produced four false positives out of twelve: "gate"
    fired on "Default Gateway" and "Aggregate Functions", "rsa" inside
    "Traversal", and "pipelin" on HTTP pipelining -- all correctly filed
    where they were.

    A term written with a trailing "*" is a deliberate prefix, matched at a
    word start so it still catches inflections ("decidab*" -> decidable,
    decidability). Everything else must match as a whole word.
    """
    if term.endswith("*"):
        return re.search(rf"\b{re.escape(term[:-1])}", haystack) is not None
    return re.search(rf"\b{re.escape(term)}\b", haystack) is not None


def _normalise(name: str) -> str:
    text_ = name.lower()
    text_ = re.sub(r"[^a-z0-9 ]+", " ", text_)
    text_ = _FILLER.sub(" ", text_)
    # Crude singularisation: enough to match "Representations" with
    # "Representation" without pulling in a stemming dependency.
    words = [w[:-1] if len(w) > 4 and w.endswith("s") else w
             for w in text_.split()]
    return " ".join(sorted(words))


def find_duplicate_concepts(db, subject: str | None) -> list[dict]:
    """Concepts under one topic whose names normalise to the same thing."""
    rows = db.execute(text("""
        SELECT s.slug, s.name, t.id, t.name, c.id, c.name,
               (SELECT count(*) FROM feed_cards f WHERE f.concept_id = c.id)
        FROM concepts c
        JOIN topics t ON t.id = c.topic_id
        JOIN subjects s ON s.id = c.subject_id
        ORDER BY s.slug, t.id, c.sequence
    """)).all()

    grouped: dict[tuple[int, str], list[tuple]] = defaultdict(list)
    for subj_slug, _subj, topic_id, topic_name, cid, cname, cards in rows:
        if subject and subj_slug != subject:
            continue
        grouped[(topic_id, _normalise(cname))].append(
            (cid, cname, cards, topic_name, subj_slug)
        )

    findings = []
    for (_topic_id, _key), members in grouped.items():
        if len(members) < 2:
            continue
        findings.append({
            "subject": members[0][4],
            "topic": members[0][3],
            "members": [
                {"id": m[0], "name": m[1], "cards": m[2]} for m in members
            ],
        })
    return findings


def find_misfiled_concepts(db, subject: str | None) -> list[dict]:
    """Concepts whose wording belongs to a different subject."""
    rows = db.execute(text("""
        SELECT s.slug, t.name, c.id, c.name,
               (SELECT count(*) FROM feed_cards f WHERE f.concept_id = c.id)
        FROM concepts c
        JOIN topics t ON t.id = c.topic_id
        JOIN subjects s ON s.id = c.subject_id
        ORDER BY s.slug, c.id
    """)).all()

    findings = []
    for subj_slug, topic_name, cid, cname, cards in rows:
        if subject and subj_slug != subject:
            continue
        lowered = cname.lower()
        own = SUBJECT_VOCAB.get(subj_slug, set())
        if any(_matches(term, lowered) for term in own):
            continue  # clearly belongs where it is

        for other, terms in SUBJECT_VOCAB.items():
            if other == subj_slug:
                continue
            hit = next((t for t in terms if _matches(t, lowered)), None)
            if hit:
                findings.append({
                    "concept_id": cid, "concept": cname,
                    "currently_in": subj_slug, "topic": topic_name,
                    "looks_like": other, "matched_on": hit, "cards": cards,
                })
                break
    return findings


def find_thin_topics(db, subject: str | None) -> list[dict]:
    """Topics with no questions, which usually means misfiled content."""
    rows = db.execute(text("""
        SELECT s.slug, ch.name, t.id, t.name,
               (SELECT count(*) FROM questions q WHERE q.topic_id = t.id),
               (SELECT count(*) FROM feed_cards f WHERE f.topic_id = t.id),
               (SELECT count(*) FROM concepts c WHERE c.topic_id = t.id)
        FROM topics t
        JOIN subjects s ON s.id = t.subject_id
        LEFT JOIN syllabus_chapters ch ON ch.id = t.chapter_id
        ORDER BY s.slug, t.sequence
    """)).all()

    findings = []
    for subj_slug, chapter, tid, tname, nq, nc, ncon in rows:
        if subject and subj_slug != subject:
            continue
        if nq == 0 or ncon <= 2:
            findings.append({
                "subject": subj_slug, "chapter": chapter or "Unassigned",
                "topic_id": tid, "topic": tname,
                "questions": nq, "cards": nc, "concepts": ncon,
            })
    return findings


def report(subject: str | None = None) -> None:
    db = SessionLocal()

    print("=" * 68)
    print("TAXONOMY REVIEW -- nothing has been changed")
    print("=" * 68)

    dupes = find_duplicate_concepts(db, subject)
    print(f"\n## Suspected duplicate concepts ({len(dupes)})\n")
    if not dupes:
        print("  none found")
    for d in dupes:
        print(f"  {d['subject']} / {d['topic'][:44]}")
        for m in d["members"]:
            print(f"      [{m['id']:>4}] {m['name'][:50]:<52} {m['cards']} cards")
        keep = max(d["members"], key=lambda m: m["cards"])
        print(f"      -> suggest keeping [{keep['id']}] "
              f"(most cards), merging the rest\n")

    misfiled = find_misfiled_concepts(db, subject)
    print(f"\n## Possibly misfiled concepts ({len(misfiled)})\n")
    if not misfiled:
        print("  none found")
    for m in misfiled:
        print(f"  [{m['concept_id']:>4}] {m['concept'][:52]}")
        print(f"         in {m['currently_in']} / {m['topic'][:40]}")
        print(f"         looks like {m['looks_like']} "
              f"(matched {m['matched_on']!r}), {m['cards']} cards\n")

    thin = find_thin_topics(db, subject)
    print(f"\n## Thin topics -- no questions or <=2 concepts ({len(thin)})\n")
    if not thin:
        print("  none found")
    for t in thin:
        print(f"  {t['subject']} / {t['chapter'][:28]} / {t['topic'][:40]}")
        print(f"         {t['questions']}Q  {t['cards']} cards  "
              f"{t['concepts']} concepts")

    print("\n" + "=" * 68)
    print(f"{len(dupes)} duplicate group(s), {len(misfiled)} possibly "
          f"misfiled, {len(thin)} thin topic(s)")
    print("Nothing was modified. Tell me which to act on.")
    print("=" * 68)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default=None,
                        help="limit the report to one subject slug")
    args = parser.parse_args()
    report(args.subject)


if __name__ == "__main__":
    main()
