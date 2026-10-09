# Hybrid Autonomous Content Engine

How GateMaster produces GATE-ready content: an agentic RAG pipeline with
corrective and self-checking stages, drawing on your books, the PYQ pattern,
and the open web — always with proof.

---

## 1. What this replaces

Today's generator is a single pass: retrieve chunks → prompt → store. It
works, but it cannot do four things you need:

| Need | Today | Engine |
|---|---|---|
| Know when the library is thin | ✗ | Agent plans before writing |
| Recover from bad retrieval | ✗ | Corrective stage re-queries |
| Catch its own weak output | ✗ | Self-check grades before storing |
| Use the web with proof | ✗ unused | Grounded search with URL citations |

---

## 2. The hierarchy

Your content model needs one more level than it has. The book is laid out
**subject → chapter → topic → subtopic**, and content must group the same way
so new material slots in without reorganising anything.

```
  Subject                 Operating Systems            11
     └── Chapter          Process Synchronization      54   (Topic today)
           └── Topic      Semaphores                   NEW
                 └── Subtopic   Binary vs Counting     NEW  (Concept today)
                        │
                        ├── FeedCard   × mode × level
                        └── Question   × type × year
```

**Change**: today's `Topic` is really the book's *chapter*, and today's
`Concept` is a *subtopic*. One new level (`Topic` proper) sits between them,
and every card and question hangs off a subtopic node.

Everything carries the same three axes, so content is findable and groupable:

```
   LEVEL         foundational │ core │ advanced
   MODE          basic │ advanced │ revision
   ORIGIN        knowledge_base │ web │ hybrid
```

---

## 3. The pipeline

```
                    ┌───────────────────────────────┐
     request ──────▶│  1. PLANNER                   │
   (scroll, ask,    │  what is missing, at what     │
    top-up)         │  level, from which source?    │
                    └───────────────┬───────────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │  2. RETRIEVE                  │
                    │  knowledge base (hybrid)      │
                    └───────────────┬───────────────┘
                                    ▼
                         ┌──────────────────┐
                         │  3. GRADE        │  is this enough,
                         │  relevant?       │  and on-topic?
                         └────────┬─────────┘
                      poor ───────┤───────── good
                          ▼       │            ▼
         ┌────────────────────┐   │   ┌────────────────────┐
         │  3a. CORRECT       │   │   │  4. GENERATE       │
         │  rewrite query,    │   │   │  closed-book over  │
         │  widen scope,      │───┘   │  graded context    │
         │  or go to web      │       └─────────┬──────────┘
         └────────────────────┘                 ▼
                                      ┌────────────────────┐
                                      │  5. SELF-CHECK     │
                                      │  grounded? useful? │
                                      │  GATE-relevant?    │
                                      └─────────┬──────────┘
                                   fail ────────┤──────── pass
                                       ▼        │           ▼
                              ┌─────────────┐   │   ┌──────────────┐
                              │ retry once  │───┘   │  6. STORE    │
                              │ or discard  │       │  + citation  │
                              └─────────────┘       └──────────────┘
```

Six stages. Three of them (**grade**, **correct**, **self-check**) are what
make this corrective and self-checking rather than a single pass.

---

## 4. Stage detail

### 1 · Planner — the agentic part

Before writing anything, the agent inspects the library and decides:

```
   Input:  scope (subject/chapter/topic/subtopic) + requested level/mode
   Asks:   what already exists here?
           what order should a learner meet it in?
           is the knowledge base enough, or is this a web topic?
   Output: a plan — a list of (subtopic, level, mode, source) to produce
```

It plans in **teaching order**, which is the ordering you asked for:

```
   definition → introduction → subtopics → foundations → related concepts
   ───────────────────────────────────────────────────────────────────▶
   foundational ............ core ............ advanced
```

### 2 · Retrieve

Hybrid search already built: BM25 keyword + 3072-dim vectors, fused with
Reciprocal Rank Fusion, scoped by subject so "deadlock" in OS does not
return the DBMS answer.

### 3 · Grade — corrective RAG

A cheap model call scores the retrieved context before any card is written:

```
   relevance   does this actually cover the subtopic?     0–1
   sufficiency is there enough to teach from?             0–1
   on_level    does it match foundational/core/advanced?  0–1
```

Below threshold on any axis, the pipeline **corrects** rather than proceeds.

### 3a · Correct

Three escalating recoveries, in order:

| Problem | Fix |
|---|---|
| Query too narrow | Rewrite with synonyms, retry retrieval |
| Scope too tight | Widen to the parent chapter |
| Not in the corpus | **Go to the web**, grounded, with URL citations |

Only after all three fail does the subtopic get marked `needs_source` —
visible in the UI so you know what material to supply.

### 4 · Generate

Closed-book over the graded context. The prompt carries the retrieved
passages and nothing else, plus the level and mode being written for.

### 5 · Self-check — self RAG

The generated card is graded before storage:

```
   grounded     every claim traceable to the context?      reject if no
   useful       does this teach, or restate the question?  reject if no
   gate_fit     is this what GATE actually tests?          reject if no
   level_fit    foundational card that assumes advanced?   reject if no
```

One retry with the failure reason fed back; a second failure discards. This
is what stops a plausible-but-useless card reaching your feed.

### 6 · Store

Every card carries its proof, whichever source it came from:

```
   knowledge_base  →  file name + page number + chunk ids
   web             →  page title + URL + retrieved date
   hybrid          →  both
```

Nothing is stored without one. Already enforced; extended to web sources.

---

## 5. Web with proof

```
   agent decides a topic needs the web
            │
            ▼
   Gemini grounded search ──▶ answer + url_citation[]
            │                      │ title, uri, char offsets
            ▼                      ▼
   generate card over       store URLs on the card,
   cited passages only      shown under it in the UI
```

`generate_grounded` is already implemented in `ai/client.py` and returns
real citations — it is simply unused. The engine wires it in as the
corrective fallback and as the explicit "search the internet" path.

**Policy**: the web supplements, never overrides. A subtopic covered by your
books uses the books; the web fills gaps and adds currency (syllabus changes,
recent exam trends).

---

## 6. Feed UI

### Assistant bar — top of the feed

```
  ┌────────────────────────────────────────────────────────────┐
  │ 🔍  Ask for any topic, level or language…          [Feed ▾] │
  └────────────────────────────────────────────────────────────┘
        │
        ├── "traps in page replacement"        → feed repopulates
        ├── "explain semaphores simply"        → chat opens
        └── "हिंदी में paging समझाओ"            → chat, Hindi
```

Two output modes from one box:

| Mode | When | Result |
|---|---|---|
| **Feed** | "give me cards on X" | Feed refills with that scope |
| **Chat** | "explain X", a question | Threaded conversation, continues |

Language is part of the request: **English · हिंदी · Hinglish**.

### Card ordering

```
  ① definition  ② introduction  ③ subtopics  ④ foundations  ⑤ related
  ──────────────────────────────────────────────────────────────────▶
```

A learner meets a chapter the way a textbook presents it, so concepts map
onto each other instead of arriving at random.

### "Explain this" on every card

```
   ┌──────────────────────────────────┐
   │  [TRAP]  Convoy Effect in FCFS   │
   │  ...                             │
   ├──────────────────────────────────┤
   │  ✓ Got it   💬 Explain   → Drill │
   └──────────────────────────────────┘
                   │
                   ▼
        chat opens with this card as
        context, in your chosen language
```

Every card gets a control that opens the assistant **with that card already
in context** — so "I don't understand this" needs no retyping.

---

## 7. Storage and rotation

Every card, whatever its origin, is stored and rotated:

```
   generated ──▶ stored with provenance ──▶ shown in feed
                                               │
                                     ┌─────────┴─────────┐
                                     ▼                   ▼
                              marked "got it"      answered wrong
                                     │                   │
                                     ▼                   ▼
                            revision queue        escalation: back
                            (spaced recall)       to the top, harder
```

Nothing generated is thrown away. A card you have read returns for revision;
a concept you keep getting wrong returns sooner and at a lower level.

---

## 8. Data model changes

```
  NEW   Topic            the level between chapter and subtopic
  NEW   ContentSource    knowledge_base | web | hybrid, with its citation
  NEW   CardView         what you have seen, when, and how often
  NEW   AssistantThread  chat history, so a conversation continues
  NEW   GenerationJob    queued work, deduplicated per scope

  EXT   FeedCard         + level, + source_type, + web_citations
  EXT   Concept          renamed Subtopic, parented to Topic
```

---

## 9. Build order

| Phase | What | Unblocks |
|---|---|---|
| **A** | Hierarchy: Topic level, level axis, migration | Everything else |
| **B** | Pipeline: planner, grade, correct, self-check | Quality + autonomy |
| **C** | Web path: grounded search, URL citations | Internet content |
| **D** | Assistant: bar, chat, per-card explain, languages | The UI you described |
| **E** | Rotation: CardView, revision queue, escalation | Spaced recall |

**A is the foundation** — remapping content later is far more expensive than
getting the hierarchy right now. **B is the substance**. C–E build on both.

---

## 10. Honest constraints

**Quota.** Grade + generate + self-check is roughly 3× the calls of today's
single pass. At ~1,400/day shared with ingestion, that is about 150 cards a
day, not thousands. Mitigations: cheap model (`flash-lite`) for grading,
self-check only on first generation per subtopic, and generated cards are
permanent so the cost is paid once.

**Ingestion is still the floor.** 26 of 54 chapters have no content because
their sources are not transcribed yet. The engine cannot generate what it
cannot read; the web path softens this but does not replace your books.

**Self-check is a filter, not a proof.** It raises the floor on quality. The
citation on every card is what makes a claim auditable — that stays the real
guarantee.
