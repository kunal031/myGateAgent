# Feed Architecture

How the feed produces an endless, ordered, grounded stream of GATE content.

---

## 1. The problem, measured

| | |
|---|---|
| Cards | 383 |
| Topics with any cards | 28 of 54 |
| **Median topic** | **13 cards ≈ 0.7 pages** |
| Thinnest topic | 1 card |

At 18 cards per page, most topics end before you finish scrolling once.
Pre-generating more helps, but never finishes: 54 topics × ~8 concepts ×
3 modes × 4 card types is a moving target, and the useful depth of a topic
depends on how much source material covers it.

**So the feed cannot be a fixed library. It has to be a library plus a
generator.**

---

## 2. The shape

```
                           ┌──────────────────────┐
   you scroll  ──────────▶ │   FEED PAGE          │
   you ask the assistant   │  filters + masonry   │
                           └──────────┬───────────┘
                                      │ GET /api/feed
                                      ▼
                        ┌─────────────────────────┐
                        │   SELECTOR              │   pick what to show
                        │  mode · scope · rank    │
                        └────────┬────────────────┘
                                 │ not enough?
                                 ▼
                        ┌─────────────────────────┐
                        │   TOP-UP QUEUE          │   fill the gap
                        │  background, debounced  │
                        └────────┬────────────────┘
                                 │
                                 ▼
                        ┌─────────────────────────┐
                        │   GENERATOR             │   write new cards
                        │  grounded, cited        │
                        └────────┬────────────────┘
                                 │ reads
                                 ▼
                        ┌─────────────────────────┐
                        │   CORPUS                │   2,590 chunks
                        │  your notes + PYQ       │   from your own sources
                        └─────────────────────────┘
```

Four stages. Everything below expands one of them.

---

## 3. Selector — what to show, in what order

Three inputs decide the next page:

```
   MODE            SCOPE                 RANK
   ─────────       ─────────────         ──────────────────
   BASIC           all subjects          weakness first
   ADVANCED   ×    one subject      ×    (mistakes, escalation,
   REVISION        one topic              exam weight, freshness)
```

**Mode changes the ordering rule, not just a filter:**

| Mode | Contains | Ordered by |
|---|---|---|
| **BASIC** | Definitions, prerequisites | **Teaching sequence** — concept 1, 2, 3… |
| **ADVANCED** | Traps, edge cases, shortcuts | **Weakness** — your mistakes first |
| **REVISION** | Cards already seen | **Spaced recall** — due for review first |

BASIC walks a chapter from the start. ADVANCED surfaces what you get wrong.
That distinction is already implemented in `services/feed/ranking.py`.

**Rank score** (ADVANCED and unfiltered):

```
  score = base_weight
        + 3 × mistakes_on_this_topic      ← wrong answers pull cards up
        + escalation_level × 2            ← repeated wrongs pull harder
        + exam_weight_bonus               ← 15-mark subjects over 4-mark
        − times_already_seen              ← avoid repeating the same card
```

---

## 4. Top-up — why the feed never ends

```
  page 1   page 2   page 3   page 4 ...
  ████████ ████████ ███░░░░░ ░░░░░░░░
                       ▲        ▲
                       │        └── generated on demand, arrives later
                       └── 600px before here, top-up fires
```

**Trigger**: when remaining unseen cards for the current scope drop below
one page, the API returns `topup: "queued"` alongside the normal page.

**Behaviour**: generation runs in the background. You keep scrolling
existing cards; new ones appear as they land. No spinner, no blocking wait
— generating one card takes about 6 seconds against the rate limit, and a
visible 40-second pause mid-scroll would be worse than a short feed.

**What it generates**, in priority order:

1. Concepts in the current scope with **no cards yet** (4 of 96 today)
2. Concepts with cards in BASIC but none in ADVANCED, or vice versa
3. Additional cards for concepts where your accuracy is low
4. Topics with no concepts yet (26 of 54 — blocked on ingestion)

**Guards**, so this cannot run away:
- One in-flight job per scope; a second scroll does not queue a second job
- Daily quota is shared with ingestion and respected (`DailyQuotaExceeded`)
- Generated cards are permanent, so the same scroll is free next time
- If quota is exhausted, the feed falls back to **recycling** seen cards for
  spaced revision rather than showing an end

---

## 5. Assistant — "give me concepts from X"

```
   "I need traps on page replacement"
                 │
                 ▼
     ┌───────────────────────┐
     │  parse intent          │  subject? topic? mode? card type?
     └───────────┬───────────┘
                 ▼
     ┌───────────────────────┐
     │  existing cards?       │──yes──▶ reorder feed to show them
     └───────────┬───────────┘
                 │ no / too few
                 ▼
     ┌───────────────────────┐
     │  generate now          │  same grounded path as top-up
     └───────────┬───────────┘
                 ▼
          feed repopulates
```

The assistant is a **front door to the same machinery**, not a separate
system. It resolves a request to a scope, checks the library, and queues
generation only for what is missing. That keeps one code path grounded and
cited rather than two.

---

## 6. Grounding — the rule that does not bend

Every generated card passes three gates before it reaches the database:

```
   retrieved chunks ──▶ closed-book prompt ──▶ card
                                                │
                            ┌───────────────────┤
                            ▼                   ▼
                   quote must appear      chunk ids + page
                   in the context         stored on the card
                            │                   │
                     fail → dropped       shown in the UI
```

1. **Closed-book**: the prompt contains only retrieved chunks and an
   instruction to use nothing else
2. **Quote check**: each card must quote the line it relied on; if that
   quote is not in the retrieved context, the card is dropped
3. **Mandatory provenance**: file and page stored on every card

Already observed working: run against the silly-mistakes log, which records
errors rather than teaching concepts, generation returned **zero cards**
instead of inventing them.

---

## 7. Data model

Only two additions to what exists:

```
  Subject ──▶ Topic ──▶ Concept ──▶ FeedCard
                         (96)         (383)
                                        │
                                        ├── mode        BASIC/ADVANCED/REVISION
                                        ├── sequence    teaching order
                                        └── provenance  file + page

  NEW  CardView     which cards you have seen, and when   → REVISION + recycling
  NEW  TopupJob     one row per queued scope              → prevents duplicates
```

`CardView` is what makes REVISION mode and spaced recall possible; without
it the feed cannot tell a card you have read from one you have not.

---

## 8. Build order

| Step | What | Why first |
|---|---|---|
| **1** | Topic + mode filters in the UI | The 383 existing cards become navigable today |
| **2** | `CardView` + seen-tracking | Everything after needs it |
| **3** | Top-up queue + background generation | The endless scroll |
| **4** | REVISION mode + recycling | Quota-proof fallback |
| **5** | Assistant on the feed | Front door to the same path |

Steps 1 and 2 are small and unblock the rest. Step 3 is the substantial one.

---

## 9. What limits this

**Ingestion, not generation.** 26 of 54 topics have no concepts because
their source material is not transcribed yet. The vision pass is running
and takes about two more days; each subject it finishes makes more topics
generatable.

**Quota is shared.** Ingestion, embedding, generation and the assistant all
draw on the same ~1,400 requests/day. Top-up is deliberately background and
debounced so a long scroll session cannot starve the overnight ingest.
