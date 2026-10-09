# Feature Pipelines

One page per feature: what triggers it, what it does, where it writes.
Read alongside `CONTENT_ENGINE.md`, which covers the shared RAG stages.

---

## 0. Shared stages

Every content-producing feature reuses these. They are described once here
and referenced by name below.

```
  RETRIEVE    hybrid BM25 + vector, scoped to a syllabus node
  GRADE       is the context relevant, sufficient, on-level?     (corrective)
  CORRECT     rewrite query → widen scope → go to web            (corrective)
  GENERATE    closed-book over graded context only
  SELF-CHECK  grounded? useful? GATE-fit? level-fit?             (self-RAG)
  STORE       never without a citation
```

---

## 1. Syllabus hierarchy — Phase A

**Trigger**: operator runs `cli/build_syllabus.py`, once per subject.

```
  book (Cormen, Galvin, Sipser…)
        │
        ▼
  ① extract the table of contents          cheap: PDF outline or first pages
        │
        ▼
  ② LLM maps ToC → Chapter/Topic/Subtopic   one call per chapter
        │
        ▼
  ③ relevance filter against GATE syllabus  in_syllabus | peripheral | out
        │
        ▼
  ④ concepts per subtopic, in teaching order + level
        │
        ▼
  Chapter → SyllabusTopic → Subtopic → SyllabusConcept
```

**Why the relevance filter matters**: Cormen has chapters GATE never
examines. Marking nodes `out_of_scope` at build time means generation never
spends quota on them.

**Writes**: `chapters`, `syllabus_topics`, `subtopics`, `syllabus_concepts`.

---

## 2. Feed generation

**Trigger**: top-up queue, assistant request, or operator CLI.

```
  scope (subject | chapter | topic | subtopic) + level + mode
        │
        ▼
  ① PLANNER   which concepts here have no card at this level/mode?
        │     order them: foundational → core → advanced
        ▼
  ② for each concept:
        RETRIEVE → GRADE ──poor──▶ CORRECT ──▶ retry or web
             │                                     │
             └──good──▶ GENERATE ◀─────────────────┘
                            │
                            ▼
                       SELF-CHECK ──fail──▶ retry once, then discard
                            │
                            ▼
                         STORE  (card + level + mode + citation)
```

**Writes**: `feed_cards` with `concept_id`, `level`, `mode`, `provenance`.

---

## 3. Feed delivery

**Trigger**: user opens or scrolls the feed.

```
  GET /api/feed?subject=&chapter=&topic=&level=&mode=
        │
        ▼
  ① SELECT  filter by scope + level + mode, exclude seen (CardView)
        │
        ▼
  ② ORDER   mode decides the rule:
        │     basic     → teaching sequence (definition → … → related)
        │     advanced  → weakness first (mistakes, escalation, exam weight)
        │     revision  → spaced recall, due first
        ▼
  ③ PAGE    18 cards
        │
        ▼
  ④ remaining < 1 page?  ──yes──▶ enqueue top-up, return topup:"queued"
        │
        ▼
  response: { items, next_offset, topup }
```

**Never ends**: if generation is quota-blocked, step ① falls back to
recycling seen cards for revision rather than returning an empty page.

---

## 4. Assistant

**Trigger**: the search bar at the top of the feed, or Explain on a card.

```
  "traps in page replacement, in Hinglish"
        │
        ▼
  ① PARSE INTENT       scope? level? mode? language? output shape?
        │
        ├── output = FEED ──▶ resolve scope ──▶ feed delivery (§3)
        │                           │ too few cards?
        │                           └──▶ feed generation (§2), queued
        │
        └── output = CHAT ──▶ RETRIEVE (scoped) ──▶ GRADE
                                   │                  │ poor
                                   │                  ▼
                                   │              web, grounded
                                   ▼
                            answer in requested language,
                            with citations, thread persisted
```

**Explain on a card** is the same path with the card's concept pre-filled as
scope and the card text as context, so nothing has to be retyped.

**Writes**: `assistant_threads`, `assistant_messages`.

---

## 5. Web content, with proof

**Trigger**: CORRECT escalation, or an explicit "search the internet".

```
  concept with thin or missing coverage
        │
        ▼
  ① Gemini grounded search      tools=[google_search]
        │
        ▼
  ② returns answer + url_citation[]   title, uri, char offsets
        │
        ▼
  ③ GENERATE over the cited passages only
        │
        ▼
  ④ SELF-CHECK, same gates as knowledge-base cards
        │
        ▼
  STORE  source_type="web", citations shown under the card
```

**Policy**: the web supplements, never overrides. A concept covered by your
books uses the books. `generate_grounded` already exists in `ai/client.py`
and returns real citations; this wires it in.

---

## 6. Question bank

**Trigger**: operator CLI, after ingestion.

```
  PYQ book                          exam papers + official keys
     │                                       │
     ▼                                       ▼
  parse chapters, answer tables,      parse key tables
  worked solutions                    (Q.No | Type | Section | Key | Marks)
     │                                       │
     └───────────────┬───────────────────────┘
                     ▼
            map to syllabus node
                     ▼
            store with answer + solution + citation
                     │
                     ▼
            gaps? ──▶ GENERATE questions per concept (§2 stages)
```

Already built for the PYQ book (836 paired, zero mismatches) and the
official keys (525 answers). The remapping to the five-level hierarchy is
part of Phase A.

---

## 7. Rotation and revision

**Trigger**: marking a card read, or answering a question.

```
  card marked "got it"            question answered wrong
        │                                 │
        ▼                                 ▼
  CardView: seen_count++          MistakeRegistry: error_count++
  next_due = now + interval       escalation_level++
        │                                 │
        ▼                                 ▼
  returns in revision mode        concept's cards jump the queue,
  when due                        and a foundational card is
                                  re-inserted at level 2+
```

**Spacing**: 1 day → 3 → 7 → 21, reset on a wrong answer. Nothing generated
is discarded; a read card returns for recall, a failed concept returns
sooner and lower.

**Writes**: `card_views`, `mistake_registry`, `concept_progress`.

---

## 8. Ingestion

**Trigger**: files dropped in `data/inbox/`, then `cli/build_corpus.py`.

```
  inbox file
     │
     ▼
  hash ──▶ already ingested? ──yes──▶ skip (no-op)
     │ no
     ▼
  text layer usable? ──yes──▶ extract directly (free)
     │ no
     ▼
  render page → Gemini vision → cache per (hash, page)
     │
     ▼
  chunk with page citations ──▶ embed ──▶ searchable
```

**Measured on the current library**: 6,618 pages extract free (Cormen,
Silberschatz, Aho, Galvin, Sipser), 2,646 need vision ≈ 1.9 days at the
free-tier cap.

---

## 9. Where each feature writes

| Feature | Reads | Writes |
|---|---|---|
| Syllabus build | book ToC | `chapters`, `syllabus_topics`, `subtopics`, `syllabus_concepts` |
| Feed generation | `source_chunks`, syllabus | `feed_cards` |
| Feed delivery | `feed_cards`, `card_views` | `generation_jobs` |
| Assistant | `source_chunks`, web | `assistant_threads`, `feed_cards` |
| Question bank | PYQ book, keys | `questions` |
| Rotation | attempts | `card_views`, `mistake_registry` |
| Ingestion | `data/inbox/` | `sources`, `source_chunks`, vectors |

---

## 10. Build sequence

```
  A  hierarchy ──▶ B  pipeline ──▶ C  web ──▶ D  assistant ──▶ E  rotation
     │                 │              │           │               │
     tables done     grade/correct   grounded    bar + chat     CardView
     migration       self-check      citations   + explain      + spacing
     syllabus build
```

A is in progress: the four tables exist. Remaining in A is the migration of
existing rows and the syllabus builder that reads book contents pages.
