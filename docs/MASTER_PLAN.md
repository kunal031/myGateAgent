# GateMaster — Master Build Plan

**Target: GATE CSE 2027, 80+ marks, AIR < 100. Max 5 users. Single developer.**

This document is the contract for the whole build. It records what exists, what is
broken, the architecture we are moving to, and the phase order. Update it as we go.

---

## 1. Where we stand today (verified, not assumed)

| Thing | State |
|---|---|
| Subjects / topics in DB | 11 / 54 — good, keep |
| Questions | 5 |
| Feed cards | 6 |
| Attempts recorded | 2 |
| Vector chunks in ChromaDB | 9 (from 3 typed PDFs only) |
| Source PDFs on disk | 683 MB, 12 subject notes + PYQ/strategy |
| Handwritten note text extractable by PyMuPDF | **0 characters** — all scanned images |
| LLM integration | none installed |
| OCR toolchain | none installed |
| Git repo | none |
| `requirements.txt` | none |
| Tests | none |

### Blocking defects found in the existing code

These are repaired in Phase 0 before any feature work.

1. **RAG cannot work.** `rag_indexer.py` only calls `page.get_text()`. Every
   handwritten PDF returns empty. 683 MB of notes index to nothing.
2. **Agent is a string template.** `api/agent.py` pastes `content[:400]` from the
   top Chroma hit and appends a fixed sentence. No LLM. UI calls it "Live RAG".
3. **`\\n` in source becomes literal backslash-n.** 11 instances in `data/seeds.py`,
   5 in `api/agent.py`. Already persisted into SQLite, so a re-seed is required,
   not just a source fix.
4. **Quiz ignores all URL params.** `useSearchParams` appears nowhere. Breaks
   feed "Drill Topic", analytics "Start", and makes the entire Test page a no-op.
5. **CORS invalid.** `allow_origins=["*"]` with `allow_credentials=True` is
   rejected by browsers. `settings.CORS_ORIGINS` is defined and never used.
6. **`/api/feed` loads whole tables** and sorts in Python. Fine at 6 cards, not at 5,000.
7. **`@app.on_event("startup")`** is deprecated; move to a `lifespan` handler.
8. Minor: no question randomisation, `stats.py` counts in Python instead of SQL,
   dropdowns hardcode "12 subjects" while the DB has 11.

---

## 2. AI provider decision

**Gemini, via the `google-genai` Python SDK (`from google import genai`).**

You have a Gemini key, and it is genuinely a good fit — not a compromise:

| Need | How Gemini covers it |
|---|---|
| Read handwritten scanned notes | `gemini-3.8-flash` is multimodal; vision transcription to Markdown + LaTeX |
| Generate feed cards & questions | Same model, structured JSON output |
| Live web feed from GATE sites | **Google Search grounding**, built in — returns `url_citation` annotations with character offsets |
| 3-language assistant | Strong Hindi + English; Hinglish works with explicit prompting |

The Search-grounding citations are the important part. Each cited text span comes
back with `url`, `title`, `start_index`, `end_index`. That is a *mechanical*
anti-hallucination guarantee for live content, not a prompt-based hope.

**Model roles** (single constant file, `backend/app/ai/models.py`, so swapping is one edit):
- `gemini-3.8-flash` — OCR transcription, card generation, question generation, assistant
- `gemini-3.5-flash-lite` — cheap classification/tagging passes

**Free-tier limits to design around:** ~10 RPM, ~1,500 requests/day for Flash;
Search grounding ~500 requests/day. Implication: ingestion **must** be a resumable
batch job with on-disk caching and rate limiting — never a blocking request path.
Verify your own limits in AI Studio; they change.

---

## 3. Anti-hallucination: the core rule

> **No card and no question enters the database without a verifiable source reference.**

Enforced structurally, not by prompting:

- `sources` table — every ingested file (book, PYQ book, handwritten notes)
- `source_chunks` table — page-level text with `source_id` + `page_number`
- Every `FeedCard` and `Question` row carries **`provenance` (required, NOT NULL)**:
  either `chunk_ids` it was generated from, or `url_citation`s from Search grounding.
- Generation is **closed-book**: the prompt contains only retrieved chunk text and
  an instruction to use nothing else. If the chunks do not support a card, the model
  must return `insufficient_context`, which we log and skip.
- A `review_status` column (`pending` / `approved` / `rejected`). You can approve in
  bulk, but the column exists so bad cards are correctable, not permanent.
- The UI shows the citation on every card. If you cannot see where a claim came
  from, that is a bug.

---

## 4. Target architecture

Driving constraint from your brief: *small files, one concern each, folders grouped
so navigation is obvious.* Hard rule — **no file over ~200 lines**. If one grows, split it.

```
backend/app/
├── main.py                     # app assembly only, no logic
├── core/
│   ├── config.py               # settings + .env
│   ├── database.py
│   └── lifespan.py             # startup/shutdown (replaces on_event)
├── models/                     # one file per domain group
│   ├── syllabus.py             # Subject, Topic, Concept
│   ├── content.py              # FeedCard, Question
│   ├── sources.py              # Source, SourceChunk
│   ├── progress.py             # Attempt, MistakeRegistry, Escalation
│   └── tracker.py              # SyllabusProgress, RevisionLog
├── schemas/                    # Pydantic request/response, mirrors models/
├── api/                        # thin HTTP layer — validate, delegate, return
│   ├── syllabus.py   feed.py   quiz.py    stats.py
│   ├── assistant.py  sources.py  tracker.py  modes.py
├── services/                   # business logic, no HTTP imports
│   ├── retrieval/              # hybrid search, NO vector database
│   │   ├── embeddings.py       # Gemini embeddings -> .npy store
│   │   ├── keyword.py          # SQLite FTS5 + BM25
│   │   ├── hybrid.py           # Reciprocal Rank Fusion of both
│   │   └── index.py            # resumable index build + stats
│   ├── feed/
│   │   ├── ranking.py          # weight + mistake boost, SQL-side
│   │   ├── modes.py            # BASIC / ADVANCED / REVISION selection
│   │   └── analysis.py         # feed composition analytics
│   ├── scoring/
│   │   ├── engine.py           # MCQ/MSQ/NAT marking (exists, keep — it is correct)
│   │   └── escalation.py       # repeated-mistake ladder
│   ├── progress/
│   │   ├── tracker.py          # syllabus completion %
│   │   └── analytics.py        # per-category performance
│   └── ingestion/
│       ├── pdf_pages.py        # PDF -> page PNGs
│       ├── transcribe.py       # page PNG -> Markdown+LaTeX via Gemini vision
│       ├── chunker.py          # text -> chunks + metadata
│       ├── indexer.py          # chunks -> ChromaDB
│       └── pipeline.py         # orchestration, resumable, rate-limited
├── ai/
│   ├── client.py               # Gemini client, retry, rate limit
│   ├── models.py               # model ID constants
│   ├── prompts/                # one .py per prompt, version-controlled
│   │   ├── transcribe.py  card_basic.py  card_advanced.py
│   │   ├── question_gen.py  assistant.py  web_feed.py
│   └── generation/
│       ├── cards.py            # closed-book card generation
│       ├── questions.py        # PYQ-grounded question generation
│       └── web_feed.py         # Search-grounded live feed
└── cli/                        # operator scripts, run manually
    ├── ingest.py  generate_cards.py  reseed.py
```

```
frontend/src/
├── app/                        # routes: thin, compose features/
│   ├── feed/  quiz/  test/  analytics/  tracker/  sources/
├── features/                   # the real UI code, by feature
│   ├── feed/       components + hooks
│   ├── quiz/       components + hooks
│   ├── assistant/  floating panel, language switch
│   ├── tracker/    syllabus tree, progress bars
│   └── analytics/  feed analysis + performance charts
├── components/ui/              # shared primitives only
├── lib/
│   ├── api/                    # one file per backend domain
│   └── types/                  # one file per domain, mirrors schemas/
└── styles/
```

---

## 5. Features, as specified

### 5.1 Three study modes

A `mode` dimension on content, driving selection:

| Mode | Contains | Source emphasis |
|---|---|---|
| **BASIC** | Foundational concepts, definitions, prerequisites. "Know what this topic even is." | Textbooks |
| **ADVANCED** | Everything GATE actually tests repeatedly: traps, formulas, edge cases, high-yield derivations | Textbooks + AIR-50 handwritten notes + PYQ patterns |
| **REVISION + QUESTION HOUR** | Rapid recall of cards already seen, then GATE-mode questions on those exact cards | PYQ books |

**Ordering within a mode (implemented).** A topic is broken into ordered
`Concept` rows, each with a `sequence` and declared prerequisites. In BASIC
mode the feed is ordered by that teaching sequence, not by rank — opening a
chapter for the first time starts at the beginning and walks forward. In
ADVANCED mode, mistake-weighted ranking takes over, which is what surfaces
weak areas first once the basics are known.

Gating is advisory, not locked — BASIC completion on a topic unlocks a
recommendation to advance, you can always override.

**Generation is grounded, and refuses when sources are thin.** Three
mechanisms, structural rather than prompt-based: generation is closed-book
over retrieved chunks only; each card must quote its supporting line, and a
card whose quote is absent from the context is dropped before saving; every
stored card carries its source chunk ids and page citation. Observed working
— run against the silly-mistakes log (which records errors rather than
teaching concepts), the model returned zero cards instead of inventing
them.

### 5.2 Escalation system

Table `escalation_state`, keyed by `(topic_id, concept_id)`:

```
level 0  normal rotation
level 1  2 consecutive wrong  -> card re-inserted next session, 3x feed weight
level 2  4 wrong              -> BASIC card forced back in, prerequisite re-taught
level 3  6 wrong              -> topic flagged RED in tracker; assistant proactively
                                 offers a from-scratch explanation in your language
de-escalate: 2 consecutive correct drops one level
```
Escalation drives feed weight, so it is self-correcting: your weak areas rise to the
top automatically. This generalises the `MistakeRegistry` boost that already works.

### 5.3 AI assistant (top of UI, on demand)

- Floating panel on every page, context-aware (knows current card/question/topic)
- **Language: English / हिंदी / Hinglish** — persisted preference, applied per request
- Grounded in your own indexed notes first, then textbooks; cites what it used
- Explicitly allowed to say "your notes don't cover this" rather than invent

### 5.4 Two analytics surfaces

**Feed analysis** — composition of what you are being shown: cards by subject,
topic, concept, card type, mode; coverage gaps; which topics have thin content.

**Performance analytics** — how you *respond*: accuracy by subject / topic /
concept / card type / mode / difficulty; time-per-question distributions;
escalation counts; mistake→mastery conversion rate; projected marks vs the 80+ target.

### 5.5 Syllabus tracker

Adds a third level below Topic: **Concept** (the atomic unit). Per concept, tracked:
`not_started / learning / learned / revised / mastered`, revision count, last-revised
date, accuracy, escalation level. Rolls up to topic → subject → overall completion %,
with separate *coverage* and *revision* percentages — they are different numbers and
conflating them is how people fool themselves.

### 5.6 Continuous content ingestion (drop-in, any time)

You will keep adding material — new books, new PYQ sets, fresh handwritten notes,
DOCX handouts — for the next year. So ingestion is **not** a one-time import; it is
a standing intake system. Design consequences:

**Drop folder, watched.** `backend/data/inbox/` is the single place you put anything.
Run `python -m app.cli.ingest` (or hit `POST /api/sources/ingest`) and it processes
whatever is new. Nothing has to be named a particular way; you classify after upload
in the UI if auto-detection guesses wrong.

**Formats accepted:** PDF (text-layer *and* scanned), DOCX, PPTX, TXT, MD, and images
(JPG/PNG of a page or whiteboard). One extractor per format behind a common interface,
so adding a format later is a single new file in `services/ingestion/extractors/`.

**Content-hash deduplication.** Every file gets a SHA-256. Re-dropping the same PDF
is a no-op; a *modified* file is detected as a new version, and only the changed pages
are re-transcribed. This is what makes repeat drops cheap instead of re-burning your
whole API quota.

**Incremental and resumable.** Per-page transcription cached on disk by
`(file_hash, page_number)`. Interrupt the job any time; rerunning continues where it
stopped. Pages already done are never re-sent to the API.

**Versioning, not overwriting.** `sources` carries `version` and `superseded_by`.
When you drop an updated edition, old cards keep pointing at the exact page they
were generated from, so existing citations never silently break. New generation
prefers the newest version.

**Regeneration is incremental too.** After new material lands, `generate_cards.py`
only touches concepts whose underlying chunks changed or that have thin coverage —
it does not regenerate the world. Your reviewed, approved cards stay put.

**Status visible in the UI.** `/sources` lists every file: pages, chunks, transcription
progress, cards and questions derived from it, and any pages that failed. A drop that
silently half-worked is the main failure mode here, so this page exists to make that
impossible to miss.

### 5.7 Live web feed

You supply trusted GATE sites. A Search-grounded job fetches genuinely relevant
recent content, and every resulting card keeps its `url_citation`s. Stored
separately with `source_type = WEB` so it never mixes with book-grounded content.
Rate-limited to stay inside the ~500/day grounding budget.

---

## 6. Build order

### Phase 0 — Foundation repair — **DONE** (branch `feat/phase-0-foundation`)
- [x] `git init`, `.gitignore`, monorepo (removed the nested `frontend/.git`)
- [x] `requirements.txt` pinned + `.env.example`
- [x] `\n` escaping fixed + `cli/reseed.py` (study history preserved)
- [x] `useSearchParams` wired into quiz — un-breaks 3 nav paths + the Test page
- [x] **Cartesian-product join bug fixed** (found during verification, not in the
      original audit: quiz served 3 of 5 questions, feed 30 rows for 6 cards)
- [x] CORS restricted to real origins; `lifespan` replaces `on_event`
- [x] Settings read `.env`; `/api/health` reports `gemini_configured`
- [x] eslint 0 errors / 0 warnings; `tsc` clean; `next build` passes
- [ ] Feed ranking into SQL — deferred to Phase 1 with the new schema

Still open from the audit, by design: the agent remains a string template
(replaced in Phase 4) and RAG still cannot read handwriting (Phase 1).

### Phase 1 — Continuous source ingestion
Schema for `sources` / `source_chunks` with hashing + versioning · `data/inbox/` drop
folder · extractors for PDF, DOCX, PPTX, TXT, MD, images · PDF→PNG · Gemini vision
transcription with on-disk cache, resume, and rate limiting · chunker with page
citations · ChromaDB indexer · `cli/ingest.py` with progress output · `/sources`
upload and status UI.
*Gate: your handwritten notes are searchable with correct page citations, and
re-dropping a file is a no-op rather than a duplicate.*

### Phase 2 — Grounded generation
Closed-book card generation per concept per mode · PYQ-grounded question generation ·
`provenance` NOT NULL enforced · review queue UI.
*Gate: 100+ cards and 100+ questions, every one citing a real page.*

### Phase 3 — Modes, escalation, tracker
Concept model + mode selection · escalation ladder · syllabus tracker UI.

### Phase 4 — Assistant
Gemini chat, 3 languages, context-aware, grounded + cited.

### Phase 5 — Analytics
Feed analysis + performance analytics, both surfaces.

### Phase 5b — Mobile-first redesign, light theme *(newly scoped)*

**Design direction: light theme**, following Dribbble shot 26961414 ("School
Education Mobile App"); reference screenshot goes in `docs/design/`. This
replaces the current dark slate-950 shell, so all five existing pages are
restyled. Mobile is the primary target, desktop the wider case.

The current shell is desktop-only: `layout.tsx` sets `ml-64` unconditionally and
the sidebar is `w-60 fixed`, so on a 390px phone 256px of 390px is margin,
leaving ~134px usable. There is no hamburger, drawer, or mobile nav, and only 10
responsive breakpoints exist across the app. Needs: collapsible drawer nav,
responsive shell, touch-sized quiz option targets, and horizontally scrollable
KaTeX blocks.

### Phase 6 — Real test engine
The genuinely missing Phase-2-from-the-old-README: 65-question palette, 3-hour timer,
virtual calculator, section timing, full scoring report.

### Phase 7 — Live web feed
Site allowlist, Search-grounded generation, citation storage.

---

## 7. What I need from you, and when

| When | What |
|---|---|
| Before Phase 0 ends | Gemini API key → `backend/.env` as `GEMINI_API_KEY` (never committed) |
| Before Phase 1 | A *first batch* of books — textbook and PYQ book for one or two subjects is enough to validate the pipeline. Drop into `backend/data/inbox/`. |
| Any time after | Everything else, whenever you have it. The inbox is permanent; drop files in and re-run ingest. No re-setup needed. |
| Before Phase 1 | Confirm the AIR-50 handwritten notes already in `data/documents/` are the ones you meant |
| Before Phase 7 | The GATE website list |

---

## 8. Preparation suggestions (you asked)

From what the codebase and your targets imply — act on these independently of the app:

1. **PYQ-first, always.** 35 years of GATE CSE repeats relentlessly. The app should
   bias toward PYQ-grounded questions over generated ones; generated questions are
   for drilling *variants* once the original is mastered, not for first contact.
2. **Weight your effort by marks, not by interest.** Your own syllabus data says
   Aptitude 15 + Engg Maths 13 = **28 marks** — more than Algorithms + TOC + COA
   combined. Most CSE aspirants under-prepare aptitude because it feels unserious.
   At 80+, you cannot leave those on the table. The tracker should show marks-weighted
   completion, not topic-count completion.
3. **The Silly_Mistakes_Log.pdf in your notes folder is the highest-value file there.**
   An AIR-50 student kept it for a reason. We should ingest it first and let it seed
   TRAP cards directly.
4. **Working 9–7 means your constraint is recall, not exposure.** Two 25-minute
   active-recall sessions beat one 3-hour passive read. The feed + escalation design
   is built for this — trust it over re-reading.
5. **Full mocks under real timing from early on, not "once I finish the syllabus."**
   Exam-day failure modes (time allocation, when to abandon a question, calculator
   fumbling) are separate skills from knowing content, and they take longer to fix.
   This is why Phase 6 matters more than it looks.
6. **Track accuracy *after* revision separately from first-attempt accuracy.** First
   attempt measures learning; post-revision measures retention. Only the second one
   predicts your GATE score.

---

## 9. Decisions already locked

- Gemini (`google-genai`), `gemini-3.8-flash` primary
- Claude-vision-style page transcription, done with Gemini vision
- Pre-generated reviewed feed **and** live Search-grounded web feed (both)
- Provenance mandatory on all generated content
- **No vector database, no cloud database.** Measured: the corpus is ~1,800
  chunks (~6 MB text); brute-force search over 2,000 x 3072-dim vectors takes
  0.38 ms, so an HNSW index is pure overhead. ChromaDB cost 316 MB RSS and
  246 MB disk (onnxruntime + a 166 MB local model) and was removed. Vectors
  live in a `.npy` file; keyword search uses SQLite FTS5; results are fused
  with RRF. SQLite stays as the database -- 5 users, single writer, and the
  whole study history is one copyable file. A cloud DB would add network
  latency to every request, which *hurts* mobile responsiveness.
- Embeddings via `gemini-embedding-001` at ingest time only, cached; query
  embeddings cached on disk (700 ms -> 0.2 ms). `semantic=false` gives a
  keyword-only path (~7 ms) when quota is exhausted.
- Small modular files, feature-grouped folders, ~200-line ceiling
- Monorepo: one git repo at the project root (the nested `frontend/.git` scaffold
  repo from create-next-app was removed; it held only the boilerplate commit)
- Ingestion is continuous and idempotent: drop files into `data/inbox/` any time
