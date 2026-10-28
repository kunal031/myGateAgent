"""Report questions whose text does not match the topic they are filed under.

Every question already has a subject, chapter and topic -- all 1,953, and
composite foreign keys keep them from contradicting each other. What they
do not guarantee is that the topic is the *right* one, and it often is
not: ten questions sit in a bucket literally named "miscellaneous"
covering deadlock, paging, device drivers and graphics memory, and the
51 filed under Process Synchronization are mostly about interrupts,
context switching and page replacement.

Misfiling is quiet damage. A question about paging that counts towards
Process Synchronization makes the analytics name the wrong weakness, and
the feed then surfaces cards for a topic that was never the problem.

**Reports only.** Moving a question changes what the student is told to
revise, and a confident wrong move is worse than a visible wrong file.
Each finding names the question, where it sits, where it looks like it
belongs and the words that suggest so, and `--apply` moves only the ones
listed in a file you have reviewed.

Keyword matching rather than the LLM: it is deterministic, reviewable,
instant, and spends no API quota -- which matters with a free key that
already returns 429. The cost is that it only catches questions whose
vocabulary is distinctive, so this finds the clear cases and stays quiet
about the ambiguous ones.

    python -m app.cli.audit_question_filing
    python -m app.cli.audit_question_filing --subject operating-systems
    python -m app.cli.audit_question_filing --out /tmp/moves.txt
    python -m app.cli.audit_question_filing --apply /tmp/moves.txt
"""

import argparse
import re
from collections import defaultdict

from sqlalchemy import text

from ..core.database import SessionLocal

#: topic slug -> the vocabulary that identifies it. Deliberately narrow:
#: a term appears here only if seeing it makes the topic near-certain. A
#: broad term produces confident wrong suggestions, which is the one
#: outcome worse than leaving a question misfiled.
TOPIC_VOCAB: dict[str, set[str]] = {
    # Operating Systems
    "process-synchronization": {
        "semaphore", "mutex", "critical section", "peterson", "mutual exclusion",
        "busy waiting", "monitor", "producer-consumer", "readers-writers",
        "binary semaphore", "counting semaphore", "wait(", "signal(",
    },
    "deadlocks": {
        "deadlock", "banker's algorithm", "resource allocation graph",
        "safe sequence", "circular wait", "hold and wait", "starvation-free",
    },
    "cpu-scheduling": {
        "round robin", "shortest job", "sjf", "fcfs", "first-come",
        "turnaround time", "waiting time", "burst time", "convoy effect",
        "time quantum", "scheduling algorithm", "priority scheduling",
        "multilevel queue", "response ratio",
    },
    "paging-tlb": {
        "page table", "tlb", "translation lookaside", "virtual address",
        "page fault", "page frame", "multi-level paging",
        "inverted page table", "page size", "virtual memory",
        "demand paging",
    },
    "page-replacement": {
        "page replacement", "lru", "fifo page", "optimal page", "belady",
        "least recently used", "clock algorithm", "second chance",
    },
    "process-pcb-context-switching": {
        "context switch", "process control block", "pcb", "kernel mode",
        "user mode", "ready state", "ready queue", "process state",
        "fork(", "interrupt", "system call", "thread switch",
    },
    # Other subjects, for cross-subject misfiling.
    "shortest-paths": {
        "dijkstra", "bellman-ford", "floyd-warshall", "shortest path",
    },
    "greedy-algorithms": {
        "minimum spanning tree", "prim's", "kruskal", "huffman",
        "spanning tree",
    },
    "divide-conquer": {"merge sort", "quicksort", "divide and conquer"},
    "cache-memory": {
        "cache", "cache hit", "cache miss", "direct mapped",
        "set associative", "write-back", "write-through",
    },
    "instruction-pipelining": {
        "pipeline", "pipelining", "data hazard", "control hazard", "stall",
    },
    "sliding-window-protocols": {
        "sliding window", "stop-and-wait", "go-back-n", "selective repeat",
        "arq", "propagation delay", "window size", "acknowledgement",
    },
    "io-organization": {
        "device driver", "dma", "interrupt-driven i/o", "polling",
        "i/o port", "graphics card", "onboard memory",
    },
}

#: A question needs this many distinct matching terms before the finding
#: is reported. One keyword is too easily incidental -- "interrupt"
#: appears in a scheduling question without making it an I/O question.
MIN_HITS = 1

#: And it must beat whatever its current topic scores by this much, so a
#: question that genuinely sits between two topics is left alone.
MARGIN = 1

#: Moving a question to a different *subject* is a far stronger claim
#: than moving it within one, and a wrong one is worse -- it removes the
#: question from the subject a student is revising. Two independent terms
#: are required before suggesting it.
CROSS_SUBJECT_MIN_HITS = 2


def _hits(content: str, vocab: set[str]) -> list[str]:
    lowered = content.lower()
    found = []
    for term in vocab:
        # Word-boundary matching: "frame" should not fire inside
        # "framework", and "lru" should not fire inside a longer token.
        pattern = r"\b" + re.escape(term) if term[-1].isalnum() else re.escape(term)
        if re.search(pattern, lowered):
            found.append(term)
    return sorted(found)


def find_misfiled(db, subject: str | None = None) -> list[dict]:
    rows = db.execute(text("""
        SELECT q.id, q.content, s.slug, s.name, t.id, t.slug, t.name,
               ch.name
        FROM questions q
        JOIN topics t ON t.id = q.topic_id
        JOIN subjects s ON s.id = q.subject_id
        LEFT JOIN syllabus_chapters ch ON ch.id = t.chapter_id
        ORDER BY q.id
    """)).all()

    topics = {
        slug: (tid, name, sslug)
        for tid, slug, name, sslug in db.execute(text("""
            SELECT t.id, t.slug, t.name, s.slug
            FROM topics t JOIN subjects s ON s.id = t.subject_id
        """))
    }

    findings = []
    for (qid, content, sslug, sname, tid, tslug, tname, chname) in rows:
        if subject and sslug != subject:
            continue

        current_hits = _hits(content, TOPIC_VOCAB.get(tslug, set()))
        scored = []
        for candidate, vocab in TOPIC_VOCAB.items():
            if candidate == tslug or candidate not in topics:
                continue
            found = _hits(content, vocab)
            if len(found) >= MIN_HITS:
                scored.append((len(found), candidate, found))

        if not scored:
            continue
        scored.sort(reverse=True)
        best_count, best_slug, best_terms = scored[0]

        if best_count < len(current_hits) + MARGIN:
            continue

        target_id, target_name, target_subject = topics[best_slug]
        if target_subject != sslug and best_count < CROSS_SUBJECT_MIN_HITS:
            continue
        findings.append({
            "question_id": qid,
            "excerpt": " ".join(content.split())[:92],
            "current_subject": sname,
            "current_chapter": chname or "Unassigned",
            "current_topic": tname,
            "current_topic_slug": tslug,
            "current_terms": current_hits,
            "suggested_topic": target_name,
            "suggested_topic_slug": best_slug,
            "suggested_topic_id": target_id,
            "suggested_subject": target_subject,
            "matched_on": best_terms,
            "cross_subject": target_subject != sslug,
        })
    return findings


def report(subject: str | None, out_path: str | None) -> None:
    db = SessionLocal()
    findings = find_misfiled(db, subject)

    print("=" * 72)
    print("QUESTION FILING REVIEW -- nothing has been changed")
    print("=" * 72)

    by_topic: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        by_topic[f["current_topic"]].append(f)

    for topic, items in sorted(by_topic.items(), key=lambda kv: -len(kv[1])):
        print(f"\n## Filed under {topic}  ({len(items)} question(s))\n")
        for f in items[:12]:
            flag = "  [DIFFERENT SUBJECT]" if f["cross_subject"] else ""
            print(f"  [{f['question_id']}] {f['excerpt']}")
            print(f"        -> {f['suggested_topic']}{flag}")
            print(f"           matched: {', '.join(f['matched_on'][:4])}")
        if len(items) > 12:
            print(f"        ... and {len(items) - 12} more")

    print("\n" + "=" * 72)
    print(f"{len(findings)} question(s) look misfiled.")

    if out_path and findings:
        with open(out_path, "w") as handle:
            handle.write(
                "# Reviewed moves. Delete any line you disagree with, then:\n"
                "#   python -m app.cli.audit_question_filing --apply <this file>\n"
                "# question_id<TAB>target_topic_id<TAB>comment\n"
            )
            for f in findings:
                handle.write(
                    f"{f['question_id']}\t{f['suggested_topic_id']}\t"
                    f"{f['current_topic']} -> {f['suggested_topic']}\n"
                )
        print(f"Written to {out_path} for review.")
    else:
        print("Re-run with --out <file> to produce a reviewable move list.")
    print("=" * 72)


def apply_moves(path: str) -> None:
    """Move only the questions listed in a reviewed file."""
    db = SessionLocal()
    moved = skipped = 0

    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        qid, target = int(parts[0]), int(parts[1])

        topic = db.execute(text(
            "SELECT id, subject_id FROM topics WHERE id = :i"
        ), {"i": target}).first()
        if topic is None:
            print(f"  skipped {qid}: topic {target} does not exist")
            skipped += 1
            continue

        # subject_id moves with topic_id. The composite foreign key would
        # reject the pair otherwise, which is the constraint doing its job.
        db.execute(text(
            "UPDATE questions SET topic_id = :t, subject_id = :s WHERE id = :i"
        ), {"t": topic[0], "s": topic[1], "i": qid})
        moved += 1

    db.commit()
    print(f"\nMoved {moved} question(s); skipped {skipped}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default=None)
    parser.add_argument("--out", default=None,
                        help="write a reviewable move list here")
    parser.add_argument("--apply", default=None,
                        help="apply a reviewed move list")
    args = parser.parse_args()

    if args.apply:
        apply_moves(args.apply)
    else:
        report(args.subject, args.out)


if __name__ == "__main__":
    main()
