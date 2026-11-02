"""Import GATE previous-year questions from practicepaper.in.

The page embeds its whole quiz as JSON -- question text, options, the
correct answer, a worked solution, the year, the set and the topic. No
AJAX call and no nonce, so 389 Operating Systems questions cost 78 page
fetches rather than the ~470 I first assumed.

That assumption was wrong because I inspected `questions[0]`, which is a
NAT. NATs legitimately carry no options, and I generalised from one
sample. The three shapes are:

    MCQ   options[], correct: 1              -> "B"
    MSQ   options[], correctSet: [0, 1, 2]   -> "A,B,C"
    NAT   ansMin / ansMax                    -> "9.5", with tolerance

Their maths is wrapped in [latex]...[/latex], which KaTeX does not know.
It is converted to the $...$ the rest of the app already renders, rather
than left to show as literal markup -- the bug just fixed in practice
mode.

Topics are mapped by name against the existing taxonomy and **never
guessed**: an unmapped topic is reported and its questions skipped. A
question filed under the wrong topic is counted towards the wrong
weakness, and the audit that found 72 such rows was expensive enough
that importing more is not worth the convenience.

    python -m app.cli.import_practicepaper --dry-run
    python -m app.cli.import_practicepaper --pages 3
    python -m app.cli.import_practicepaper
"""

import argparse
import json
import re
import time

import httpx
from sqlalchemy import text

from ..core.database import SessionLocal
from ..models.models import Question, Subject, Topic

BASE = "https://practicepaper.in"

#: Source path -> the subject slug in our taxonomy. One entry for now;
#: the importer is written so other subjects are a line each.
SOURCES = {
    "/gate-cse/operating-system": "operating-systems",
}

#: Their topic name -> our topic slug. Mapped explicitly rather than
#: fuzzily: "Memory Management" is a *chapter* here, not a topic, and a
#: near-match would file a paging question under page replacement.
TOPIC_MAP = {
    "memory management": "paging-tlb",
    "virtual memory": "paging-tlb",
    "page replacement": "page-replacement",
    "process synchronization": "process-synchronization",
    "synchronization": "process-synchronization",
    "cpu scheduling": "cpu-scheduling",
    "process scheduling": "cpu-scheduling",
    "deadlock": "deadlocks",
    "deadlocks": "deadlocks",
    "process management": "process-pcb-context-switching",
    "processes and threads": "process-threads",
    "threads": "process-threads",
    "process concept": "process-pcb-context-switching",
    "inter process communication": "process-threads",
    # Surfaced once pagination was fixed; mapped by meaning, not by
    # string similarity. "Process" and "Thread" are the process-basics
    # topic, not synchronisation.
    "process": "process-pcb-context-switching",
    "thread": "process-threads",
    "system call": "process-pcb-context-switching",
    "file systems": "miscellaneous",
    "file system": "miscellaneous",
    "disk scheduling": "miscellaneous",
    "io systems": "miscellaneous",
}

#: One request a second. Their robots.txt sets no crawl-delay, which is
#: permission rather than an invitation.
DELAY_SECONDS = 1.0

_LETTERS = "ABCDEFGH"


def to_katex(raw: str) -> str:
    """Convert their [latex]...[/latex] to the $...$ MathText renders.

    Left alone, the markup shows literally -- the exact fault just fixed
    in practice mode, and importing 389 questions carrying it would have
    reintroduced it at scale.
    """
    if not raw:
        return ""
    out = re.sub(r"\[latex\](.*?)\[/latex\]", r"$\1$", raw, flags=re.S)
    # Their solutions are HTML; the app renders plain text with maths.
    out = re.sub(r"<br\s*/?>", "\n", out, flags=re.I)
    out = re.sub(r"</?(b|i|strong|em|u)>", "", out, flags=re.I)
    out = re.sub(r"<pre>|</pre>|<code>|</code>", "\n", out, flags=re.I)
    out = re.sub(r"<[^>]+>", "", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def parse_tag(tag: str) -> tuple[int | None, str | None]:
    """"GATE CSE 2026 SET-2" -> (2026, "Set 2")."""
    year = re.search(r"\b(19|20)\d{2}\b", tag or "")
    setno = re.search(r"set[\s\-_]*(\d+)", tag or "", re.I)
    return (int(year.group(0)) if year else None,
            f"Set {setno.group(1)}" if setno else None)


def fetch_page(client: httpx.Client, path: str, page: int) -> dict | None:
    """Pull one listing page and return its embedded quiz payload."""
    # ?page_no=N, which is what the palette's own links use. /page/N
    # looks plausible, is accepted, and silently serves page 1 every
    # time -- a first run wrote the same five questions 78 times.
    url = f"{BASE}{path}" + (f"?page_no={page}" if page > 1 else "")
    try:
        response = client.get(url, timeout=30, follow_redirects=True)
    except httpx.HTTPError as exc:
        print(f"    page {page}: unreachable ({str(exc)[:60]})")
        return None
    if response.status_code != 200:
        print(f"    page {page}: HTTP {response.status_code}")
        return None

    body = response.text
    start = body.find('{"meta":{"quizId"')
    if start < 0:
        return None

    # Brace-walk rather than a regex: the payload contains braces inside
    # its own strings, and a lazy regex stops at the first one.
    depth = 0
    for end in range(start, len(body)):
        if body[end] == "{":
            depth += 1
        elif body[end] == "}":
            depth -= 1
            if depth == 0:
                break
    try:
        return json.loads(body[start:end + 1])
    except json.JSONDecodeError:
        print(f"    page {page}: payload did not parse")
        return None


def to_record(q: dict) -> dict | None:
    """One payload question -> the shape _store_question expects."""
    qtype = (q.get("type") or "").upper()
    options = q.get("options") or []

    if qtype == "MCQ":
        index = q.get("correct")
        if index is None or index >= len(options):
            return None
        answer = _LETTERS[index]
    elif qtype == "MSQ":
        picked = q.get("correctSet") or []
        if not picked:
            return None
        answer = ",".join(_LETTERS[i] for i in sorted(picked)
                          if i < len(options))
    elif qtype == "NAT":
        low, high = q.get("ansMin"), q.get("ansMax")
        if low is None:
            return None
        answer = str(low)
    else:
        return None

    year, exam_set = parse_tag(q.get("tag1") or "")

    return {
        "content": to_katex(q.get("text") or ""),
        "question_type": qtype,
        "marks": int(q.get("marks") or 1),
        "options": [
            {"id": _LETTERS[i], "text": to_katex(text_)}
            for i, text_ in enumerate(options)
        ] or None,
        "correct_answer": answer,
        "nat_min": float(q["ansMin"]) if qtype == "NAT" else None,
        "nat_max": float(q.get("ansMax") or q["ansMin"]) if qtype == "NAT" else None,
        "explanation": to_katex(q.get("solution") or ""),
        "exam_year": year,
        "exam_set": exam_set,
        "their_topic": (q.get("tag2") or "").strip(),
        "source_id": q.get("id"),
    }


def run(*, pages: int | None, dry_run: bool) -> None:
    db = SessionLocal()
    client = httpx.Client(headers={
        # Identifies the client honestly rather than impersonating a
        # browser, and points at the project if they want to object.
        "User-Agent": "GateMasterBot/1.0 (personal GATE study tool)",
    })

    for path, subject_slug in SOURCES.items():
        subject = db.query(Subject).filter(Subject.slug == subject_slug).first()
        if subject is None:
            print(f"  no subject {subject_slug!r} in the taxonomy; skipping")
            continue

        topics = {
            t.slug: t for t in db.query(Topic)
            .filter(Topic.subject_id == subject.id).all()
        }

        first = fetch_page(client, path, 1)
        if not first:
            print(f"  {path}: no payload on page 1")
            continue

        total_pages = int(first["meta"].get("totalPages") or 1)
        limit = min(pages or total_pages, total_pages)
        print(f"  {path}: {first['meta'].get('totalQuestions')} questions "
              f"over {total_pages} pages; reading {limit}")

        collected: list[dict] = []
        unmapped: dict[str, int] = {}

        for page in range(1, limit + 1):
            payload = first if page == 1 else fetch_page(client, path, page)
            if page > 1:
                time.sleep(DELAY_SECONDS)
            if not payload:
                continue

            # The server confirming which page it served. Without this a
            # wrong URL pattern is invisible: every page parses, every
            # question looks valid, and the same five arrive 78 times.
            served = int(payload["meta"].get("pageNo") or 0)
            if served != page:
                print(f"    page {page}: server returned page {served}; "
                      "stopping rather than importing duplicates")
                break

            for raw in payload.get("questions") or []:
                record = to_record(raw)
                if record is None:
                    continue
                slug = TOPIC_MAP.get(record["their_topic"].lower())
                if slug is None or slug not in topics:
                    unmapped[record["their_topic"]] = (
                        unmapped.get(record["their_topic"], 0) + 1
                    )
                    continue
                record["topic"] = topics[slug]
                collected.append(record)

            if page % 10 == 0 or page == limit:
                print(f"    page {page}/{limit}: {len(collected)} usable so far")

        print(f"\n  parsed {len(collected)} question(s)")
        if unmapped:
            print("  unmapped topics (questions skipped rather than guessed):")
            for name, count in sorted(unmapped.items(), key=lambda kv: -kv[1]):
                print(f"    {name or '(none)'!r}: {count}")

        if dry_run:
            print("\n  --dry-run: nothing written\n")
            for r in collected[:3]:
                print(f"    [{r['question_type']}] {r['exam_year']} "
                      f"{r['exam_set'] or ''} -> {r['topic'].name[:30]}")
                print(f"      {r['content'][:80]}")
                print(f"      answer={r['correct_answer']} "
                      f"solution={len(r['explanation'])} chars")
            continue

        written = skipped = 0
        seen_ids: set[str] = set()
        seen_text: set[str] = set()
        for r in collected:
            # Deduped on content: these papers are republished widely and
            # some already arrived through the earlier edurev import.
            # Deduped on their question id as well as on content: the
            # id catches a repeat within this run before anything is
            # committed, which content alone did not -- the first run's
            # 390 inserts were all pending in one transaction, so none
            # could see the others.
            # Content as well as id, within this run: the site lists the
            # same question under more than one year, so two distinct
            # source ids can carry identical text. Nine such rows got
            # through a run that checked the id alone.
            marker = f"(id {r['source_id']})"
            if r["content"] in seen_text:
                skipped += 1
                continue
            if marker in seen_ids or db.execute(text(
                "SELECT id FROM questions "
                "WHERE provenance LIKE :m OR content = :c LIMIT 1"
            ), {"m": f"%{marker}", "c": r["content"]}).first():
                skipped += 1
                continue
            seen_ids.add(marker)
            seen_text.add(r["content"])

            db.add(Question(
                subject_id=subject.id,
                topic_id=r["topic"].id,
                question_type=r["question_type"],
                marks=r["marks"],
                negative_marks=(
                    0.0 if r["question_type"] in ("MSQ", "NAT")
                    else (0.33 if r["marks"] == 1 else 0.66)
                ),
                content=r["content"],
                options=json.dumps(r["options"]) if r["options"] else None,
                correct_answer=r["correct_answer"],
                nat_min=r["nat_min"], nat_max=r["nat_max"],
                explanation=r["explanation"],
                solution_source="web" if r["explanation"] else None,
                exam_year=r["exam_year"], exam_set=r["exam_set"],
                origin="WEB", is_pyq=True,
                source=f"GATE CSE {r['exam_year']}"
                       + (f" {r['exam_set']}" if r["exam_set"] else ""),
                provenance=f"{BASE}{path} (id {r['source_id']})",
                review_status="approved",
            ))
            written += 1

        db.commit()
        print(f"\n  written {written}, skipped {skipped} already present")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=None,
                        help="stop after this many pages (for a trial run)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(pages=args.pages, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
