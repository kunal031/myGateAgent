# GateMaster

A GATE CSE 2027 preparation platform built for someone preparing around a
full-time job. Target: 80+ marks, AIR under 100.

---

## Why this exists

GATE preparation assumes a student with whole days to give it. The standard
advice — read the textbook, work the problems, revise — is written for
someone with eight free hours, not someone opening a laptop at 9pm after a
9-to-7.

The constraint is not motivation. It is that scarce study time gets spent
badly:

- **Deciding what to study** costs as much as studying. Eleven subjects,
  fifty-seven topics, and no obvious entry point.
- **Revision is unguided.** Without a record of what is already known, the
  same comfortable material gets reread while weak areas go untouched.
- **The books are enormous.** Cormen is 1,100 pages; GATE examines a
  fraction of it. Finding that fraction is itself a project.
- **Mistakes evaporate.** A question got wrong in March is forgotten by
  April unless something deliberately brings it back.

This application is the attempt to solve those four problems for one
person, properly, rather than generally and badly.

There is a second reason. It is a demonstration that one person can build
something substantial end to end — ingestion, retrieval, generation,
scheduling, and a UI — rather than assembling it from services.

---

## What it does differently

**Every card cites its source.** This is the constraint the whole content
pipeline is built around. A generated card that cannot quote the page it
came from is rejected, not published with a disclaimer. At present
**1,294 cards carry a citation and none do not** — "Cormen Introduction to
Algorithms.pdf (p. 414)" rather than "according to standard references". An
AI that invents plausible GATE content is worse than no AI, because the
error is only discovered in the exam hall.

**The feed follows a dependency order, not an exam-weight order.** General
Aptitude carries the most marks, so a naive ranking puts it first. But it
depends on nothing, while Algorithms depends on discrete mathematics. The
order is the one the student actually wants to learn in: logic and sets
first, compiler design last, because parsing needs theory of computation.

**It interleaves rather than blocks.** The tidy design — march through one
concept at a time — is the one the evidence rejects. Blocked practice
improves performance *during* study and worsens it on a later test;
interleaving does the reverse, and roughly doubled test scores in Rohrer's
arithmetic studies. So a page is deliberately mixed: current work, due
reviews, and a deliberately contrasting concept. It feels less neat. It
teaches better.

**Readiness, not gating.** A concept whose prerequisites are unlearned
sinks in the ranking rather than being hidden, so jumping ahead stays
possible. The prerequisite graph is a real DAG — 282 concepts, no cycles —
and the feed walks it.

**Mistakes come back.** A wrong answer raises that concept's weight until
it is answered right, so the feed is shaped by what is not yet known rather
than by what was generated most recently.

---

## What it does

### Feed
Cards — concepts, formulas, traps, shortcuts — ordered by what is worth
studying now: curriculum position, prerequisite readiness, spaced-repetition
due dates, and recent mistakes. A header shows how far through the syllabus
you are and what to open next. Cards can be hand-written as well as
generated, and are tagged with a typed concept graph so a hover shows both
where a card sits and what else touches it.

### Quiz and Test
Both run as the real exam does: navigate freely between questions, mark for
review, submit once, and see answers only afterwards. Correct GATE scoring
throughout — MCQ −0.33/−0.66, MSQ all-or-nothing with no negative marking,
NAT with tolerance ranges. Quiz is for drilling a topic; Test evaluates
performance over a full or sectional paper.

### Question import
Paste a URL or upload a PDF and the questions are extracted, typed
(MCQ/MSQ/NAT inferred from the answer's shape, because a wrong type
silently mis-scores every attempt), and filed under a subject and topic.
Nothing is written until you review what was found and supply any missing
answers. Imports run in the background and survive closing the page.

### AI assistant
Answers from your own books first, cited to the page; falls back to grounded
web search with URLs; falls back to the model alone only as a last resort —
and says which of the three it used. Explains any card on demand, in
English, Hindi or Hinglish.

### Analytics
Accuracy, marks, and unresolved mistakes by subject, against the historical
mark distribution.

---

## The content pipeline

Study material comes from the student's own library rather than from the
model's memory:

```
  PDFs ──extract──> chunks ──embed──> pgvector
   │                                      │
   │ (vision OCR for scans)               │ hybrid retrieval
   │                                      │ (BM25 + semantic, RRF-fused)
   ▼                                      ▼
  11 books, 10,783 pages ──────────> grade ──> generate ──> verify ──> card
                                       │                        │
                                 too weak? ──> web search       │
                                                                ▼
                                                  rejected if unsupported
```

Retrieved material is graded before anything is written from it; a generated
card is checked back against its source and discarded if it cannot be
supported. Current corpus: **58 sources, 25,074 chunks, all embedded.**

---

## Tech stack

**Backend** — Python 3.11, FastAPI, SQLAlchemy 2.1, PostgreSQL 18 with
pgvector (`halfvec(3072)` + HNSW). Gemini via `google-genai` for generation,
vision OCR and embeddings. PyMuPDF for PDF extraction.

**Frontend** — Next.js 16, React 19, TypeScript, Tailwind v4, KaTeX for
mathematics.

**Retrieval** — hybrid search: PostgreSQL `tsvector` for keyword, pgvector
for semantic, fused with Reciprocal Rank Fusion. Agentic RAG: plan →
retrieve → grade → correct → generate → self-check.

Everything runs locally. The cloud database is a deployment copy, not the
source of truth.

---

## Running it

```bash
./start.sh
```

- Frontend: http://localhost:3000
- API docs: http://127.0.0.1:8000/docs

Requires PostgreSQL with the `vector` extension, and a `GEMINI_API_KEY` in
`backend/.env`. See `docs/RUNBOOK.md` for ingesting new material, generating
content, backups, and deployment.

---

## Scope

Built for one student, with a hard cap of five users. Decisions throughout
favour the single-user case — background threads rather than a task queue,
one-way sync rather than conflict resolution — because the alternative is
infrastructure nobody here needs.
