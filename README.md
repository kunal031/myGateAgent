# GateMaster

A retrieval-grounded study system for GATE CSE 2027, built for someone
preparing around a 9–7 job. Every explanation it shows is traced to a page
in a real textbook; nothing is invented.

- **Frontend** — [http://localhost:3000](http://localhost:3000)
- **API docs** — [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Start both** — `./start.sh`

---

## Why it exists

GATE rewards two things that ordinary study apps handle badly: **recall
under time pressure**, and **knowing which 20% of the syllabus carries the
marks**. A working professional has perhaps two hours an evening, which is
not enough to read everything — so the system's whole job is deciding what
to put in front of you next.

That decision needs three things the app actually has: a corpus it can cite,
a model of what you have and have not learned, and a measure of what each
gap is worth in marks.

---

## What is in it

| | |
|---|---|
| Books ingested | **58** sources |
| Corpus | **25,074** chunks, all embedded |
| Syllabus | 11 subjects → 39 chapters → 57 topics → 282 concepts |
| Study cards | **1,294** |
| Questions | **1,953** across 27 papers |

---

## Retrieval: three strategies, fused

Semantic search alone fails on GATE material. Ask for "Banker's algorithm"
and embeddings happily return passages about banking. Keyword search alone
fails the opposite way: it cannot connect "convoy effect" to a passage that
explains the idea without using the phrase.

So three retrieval paths run and their results are **fused with Reciprocal
Rank Fusion** (`RRF_K = 60`, in `services/retrieval/hybrid.py`):

```
                    ┌─ BM25 keyword  (Postgres tsvector + GIN)
  query  ──────────▶├─ Dense vector  (pgvector halfvec(3072) + HNSW)
                    └─ Metadata filter (subject / topic scoping)
                              │
                              ▼
                     Reciprocal Rank Fusion
                              │
                              ▼
                    top-k chunks, with citations
```

RRF rather than weighted score blending, because the two scores are not
comparable — a BM25 score of 12 and a cosine distance of 0.3 have no shared
scale. RRF only uses each result's *rank*, so it needs no tuning per query
type and degrades gracefully when one path returns nothing.

`halfvec` rather than `vector`: 3,072 dimensions at half precision halves
the index size with no measurable recall loss, and pgvector's HNSW supports
up to 4,000 dimensions for `halfvec` against 2,000 for `vector`.

### Agentic RAG, not single-shot

A plain retrieve-then-generate pipeline answers confidently from bad context.
The assistant (`services/assistant/`) adds steps around it:

1. **Intent parse** — classify the question and extract subject/topic scope,
   so retrieval is filtered rather than searching all 25,074 chunks.
2. **Retrieve** — hybrid search as above.
3. **Grade** — judge whether the retrieved context can actually answer the
   question. This is the step that matters: without it, the assistant
   paraphrases whatever came back.
4. **Correct** — if the corpus is insufficient, fall back to a
   **Google-Search-grounded** call rather than refusing or hallucinating.
   Answers are tagged `book`, `web` or `ai` so provenance is visible.
5. **Generate + self-check** — produce the answer with citations, then
   verify claims against the context used.

Content generation uses the same grounding: a card that cannot be built from
retrieved text raises `InsufficientContext` instead of being invented.

---

## The three study engines

### Feed engine — what to learn next

`services/feed/ordering.py` scores every candidate card and assembles a page.
It is not a reverse-chronological list; it is a scheduler.

**Scoring inputs:**

| Signal | Effect |
|---|---|
| Curriculum position | `CURRICULUM_STEP = 6.0` per subject, `TOPIC_STEP = 1.5` |
| Prerequisites unmet | `NOT_READY_PENALTY = 40.0` |
| Already mastered | `MASTERED_PENALTY = 25.0` |
| Review due | `DUE_BOOST = 18.0` |
| Repeated mistakes | `ESCALATION_BOOST = 12.0` |
| Exam weight | `WEIGHT_SCALE = 1.2` |

**Page composition** is deliberate, not a ranked top-N:

```
60%  current topic      — the thing you are learning now
25%  review             — due by spaced repetition (1, 3, 7, 21, 60 days)
15%  contrast           — a different subject
```

The 15% contrast exists because of the interleaving research: blocked
practice feels more productive during study and performs *worse* on a later
test, while interleaved practice roughly doubled scores in Rohrer's work.
A feed that only shows your current topic optimises for the wrong moment.

Prerequisites form a DAG across all 282 concepts — 238 edges, 81 roots, 5
levels deep, no cycles. A concept whose prerequisites are unlearned is
penalised rather than hidden, so a student who wants to jump ahead still
can.

### Quiz engine — practice without the exam clock

Questions filtered by subject → chapter → topic → paper. Answers are hidden
until the whole set is submitted, which is the point: revealing an answer
immediately trains recognition, and GATE tests recall.

### Test engine — the exam, faithfully

`services/exam/` reproduces GATE's actual scoring, which is where most
practice tools quietly cheat:

| Type | Marks | Negative |
|---|---|---|
| MCQ (1 mark) | +1 | **−0.33** |
| MCQ (2 mark) | +2 | **−0.66** |
| MSQ | +1 / +2 | **0** — but all-or-nothing |
| NAT | +1 / +2 | **0**, answer within tolerance |

Getting MSQ wrong is costly in the other direction: marking it as
negatively-scored teaches you to skip questions you should attempt.

Patterns include the full 65-question / 180-minute paper, subject sprints,
topic drills and custom mixes. Sessions persist, so a paper survives a
closed tab.

---

## Analytics: from "how am I doing" to "what do I fix"

Most study analytics describe. These are built to be acted on.

### The drill-down

The same four levels as the syllabus, each fetched only when opened:

```
Operating Systems          12/87 Q   cov 14%   57.1%
└─ Process Management      11/76 Q             54.5%
   ├─ Process, PCB…         4/25 Q             75.0%
   └─ Process Sync…         7/51 Q             42.9%   ← the actual problem
      └─ Semaphores, Peterson's…   0/6 cards
```

A subject row says "you are weak at Operating Systems", which is true of
everyone and actionable by no one. Two levels down it names a topic.

**Aggregates are computed per level in SQL, not summed upward.** Summing
looks equivalent until a row has a null parent, at which point the totals
silently stop matching.

### Nine analyses

`services/analytics/performance.py` — accuracy by question type, pace
(against a 90s/180s budget per mark), trend over 14 days, daily activity,
weak topics **ranked by marks at stake** rather than by accuracy,
distractor analysis, exam readiness, retention, exam behaviour.

Weak topics are ranked by `(1 − accuracy) × subject_weight`, because an
8-mark subject you fail matters more than a 1-mark one.

Every analysis has a minimum-sample floor. An accuracy drawn from three
attempts is a guess, and is reported as "not enough data" rather than a
number.

### Activity log

`activity_events` is **append-only**, and exists because the other tables
keep current state rather than history: `card_views` holds one row per card
with a rolling `last_seen_at`, so a card read on three days left one
timestamp. A day spent reading rather than answering looked empty — which
is exactly the day a streak nudge must not punish.

Each event stores all four taxonomy levels **as they were at the time**.
Refiling a concept next month must not rewrite what you did last month.

---

## Data integrity

Every content table stores shortcut columns — a question carries `topic_id`
*and* `subject_id` — so analytics can group by subject without a four-table
join. Nothing stopped them drifting apart:

```sql
UPDATE questions SET subject_id = 1   -- topic belongs to subject 9
-- Accepted. Nothing failed.
```

That question would have been counted under the wrong subject in every
query from then on. **14 composite foreign keys** now make it impossible:
`questions(topic_id, subject_id)` references `topics(id, subject_id)`, so
Postgres checks the pair.

Chosen over removing the shortcuts, which would have touched 545 references
and slowed every analytics query, for a correctness problem that had not
yet bitten.

`activity_events` is deliberately excluded — it records history, and
constraining it would force old events to follow the current taxonomy.

---

## Auth

- JWT access (30 min) + refresh (30 day), signed HS256
- `token_version` per account — bumping it signs out everywhere with no
  blacklist to sweep
- **Google OIDC** with PKCE, verified against Google's published JWKS.
  Identity keys on `sub`, never email: Google documents that an account's
  email can change while `sub` cannot, so an email key means a user who
  changes their address loses their history.
- Password registration is closed once the first account exists; new
  accounts arrive through Google, which supplies an already-verified email
  and removes any need for OTP infrastructure.

---

## Tech stack

**Backend** — FastAPI, SQLAlchemy 2.1, PostgreSQL 18 + pgvector, PyJWT,
bcrypt, Google Gemini (`google-genai`) for generation, embeddings and
Search grounding.

**Frontend** — Next.js 16, React 19, TypeScript, Tailwind v4.

**Data** — PostgreSQL everywhere: relational tables, `tsvector` full-text
and `halfvec` embeddings in one database, so a semantic search and the
filters applied to it happen in a single indexed query rather than a
round-trip to a separate vector store.

---

## Deployment

Target: **Vercel** (frontend) → **AWS Lambda** (API) → **Neon** (database).

**Database — ready.** Neon is seeded and verified: all tables row-for-row
against local, 25,074/25,074 embeddings at 3,072 dimensions, HNSW and GIN
indexes rebuilt, hybrid retrieval confirmed working, 459 MB of the 1 GB
free tier.

The engine detects Lambda via `AWS_LAMBDA_FUNCTION_NAME` and switches to
`NullPool` — a connection pool is per-process, and Lambda gives every
concurrent invocation its own process, so pooling there shares nothing and
leaves frozen instances holding connections nobody can use. Neon's
PgBouncer does the real pooling, which needs the `-pooler` hostname; the
engine warns if it is missing.

**API — not ready.** Outstanding:

- No Mangum handler or deployment config
- `api/papers.py:192` starts a daemon thread for paper import; Lambda
  freezes the environment when the handler returns, so an import would
  silently truncate. Needs to become its own function.
- Gemini assistant calls can exceed API Gateway's 29-second ceiling
- Package is 211 MB against Lambda's 250 MB limit; 114 MB once
  ingestion-only dependencies are excluded

**Ingestion cannot run on Lambda at all** — embedding a book takes hours
against a 15-minute hard limit. It runs locally against whichever database
is configured.

Docker Compose (Postgres + Redis + API + web) remains for local and
container deployment.

---

## Repository

```
backend/
  app/
    api/          HTTP handlers
    core/         config, database, auth, OAuth
    models/       SQLAlchemy models
    services/
      retrieval/  hybrid search, embeddings, index
      assistant/  agentic RAG
      feed/       ordering, progress, tagging
      exam/       patterns, scoring, sessions
      analytics/  performance, breakdown, calendar
      generation/ grounded card and question generation
      ingestion/  PDF extraction, chunking
    cli/          migrations and batch jobs
    data/         curriculum order, chapter map, traps
frontend/
  src/
    app/          routes
    features/     feed, exam, analytics, auth, profile
    lib/          API client, auth interceptor
```
