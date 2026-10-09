# Runbook

Day-to-day commands. All backend commands run from `backend/`.

---

## Start the app

```bash
./start.sh                      # from the project root; both services
```

- Frontend: http://localhost:3000
- API docs: http://127.0.0.1:8000/docs

---

## Add new material

Drop files into `backend/data/inbox/`, under the folder that fits:

```
inbox/notes/<source-name>/   handwritten or topper notes
inbox/books/                 textbooks
inbox/pyq/papers/            exam papers and answer keys
inbox/pyq/topicwise/         topic-grouped PYQ compilations
```

Then ingest. Re-dropping a file already ingested is a no-op, so this is safe
to run whenever:

```bash
./venv/bin/python -m app.cli.build_corpus --free-only   # no vision quota
./venv/bin/python -m app.cli.build_corpus               # everything
```

### The long vision pass

Scanned and handwritten pages go through Gemini vision, which is quota-bound
(~1,400 requests/day on the free tier). Run it unattended:

```bash
./app/cli/overnight.sh
tail -f data/overnight.log
```

It stops cleanly when the daily quota runs out. Running it again the next day
continues: transcribed pages are cached per page and ingested files are
skipped, so nothing is paid for twice.

---

## Generate feed content

Concepts first (the ordered breakdown of a topic), then cards per mode. The
CLI does both:

```bash
# one topic, BASIC and ADVANCED
./venv/bin/python -m app.cli.generate --topic cpu-scheduling

# a whole subject, BASIC only
./venv/bin/python -m app.cli.generate --subject operating-systems --mode BASIC
```

Idempotent at both levels: a topic that already has concepts, or a concept
that already has cards in that mode, is skipped. Re-run as more sources land.

**Generation refuses rather than inventing.** If retrieval finds too little
material for a concept, it logs `InsufficientContext` and writes no cards.
Zero cards means the corpus is thin on that topic, not that the job failed.

---

## Housekeeping

```bash
# apply new columns after a model change
./venv/bin/python -m app.cli.migrate

# rewrite seeded questions from app/data/ (keeps attempts and mistakes;
# feed cards are left alone -- they are generated and carry provenance)
./venv/bin/python -m app.cli.reseed

# remove layout placeholder cards, if any were made to test the masonry grid
./venv/bin/python -m app.cli.clear_placeholders
```

---

## Where the data lives, and keeping it

Three copies, and they are not equivalent:

| Copy | Role | Risk |
|---|---|---|
| **Local Postgres** | the working copy; `DB_TARGET=local`, everything is written here | one disk |
| **Aiven** | deployment copy, pushed from local | **free tier expires after 30 days** |
| **`data/backups/*.dump`** | cold copy on disk | only as good as the last dump |

The app never writes to Aiven directly, so local is always the source of
truth and pushing to the cloud cannot lose local work. The corpus is
expensive to rebuild -- thousands of vision OCR pages and 13k embeddings,
all paid for with API quota -- so it is worth a dump before anything
destructive and on a regular cadence.

```bash
./venv/bin/python -m app.cli.backup              # dump local Postgres
./venv/bin/python -m app.cli.backup --from-aiven # dump the cloud copy
./venv/bin/python -m app.cli.backup --list
./venv/bin/python -m app.cli.backup --restore gatemaster-local-<stamp>.dump
```

Dumps are custom-format and compressed (~180 MB at the current corpus
size), the newest 7 are kept, and `data/backups/` is gitignored. Embeddings
are included, so a restore does not mean re-embedding.

**When the Aiven trial ends**, nothing is lost: local Postgres already holds
everything. Point `POSTGRESQL_AIVEN_URI` at the replacement and re-run the
push below.

---

## Push the corpus to Aiven

Local Postgres is the working copy; Aiven is the deployment copy. Refresh it
with:

```bash
./venv/bin/python -m app.cli.migrate_to_postgres \
    --from-local --to-aiven --replace --dry-run   # always check first
./venv/bin/python -m app.cli.migrate_to_postgres \
    --from-local --to-aiven --replace
```

**`--from-local` is not optional.** Without it the source is the SQLite
file, which is a pre-ingestion backup frozen at 2,590 chunks -- running it
by accident replaces the full corpus with that snapshot, and the only
symptom is a cloud copy that quietly has less in it.

`--replace` truncates the target's tables first, so run the dry run and read
the row counts before committing to it. Columns the target lacks are added
before anything is copied, which is deliberate: `create_all` never alters an
existing table, so a target seeded before a column was added stays behind
until something reconciles it, and reconciling after a truncate would leave
the target empty on failure.

Vectors are carried from the source's `halfvec` column, not from
`data/vectors/chunks.npy` -- that store is stale as well.

Do this after a generation run finishes rather than during one, so the copy
is a consistent snapshot.

---

## Check state

```bash
curl -s localhost:8000/api/agent/index/status   # chunks, vectors, pending
curl -s localhost:8000/api/agent/sources        # per-file ingest progress
curl -s localhost:8000/api/health               # includes gemini_configured
```

Today's quota use is in `data/.ratelimit_generation.json`. It resets at
midnight local time.

---

## Where things live

| What | Where |
|---|---|
| Source files you add | `backend/data/inbox/` |
| Page transcription cache | `backend/data/transcripts/` |
| Vectors | `backend/data/vectors/` |
| Database | `backend/gatemaster.db` |
| Gemini key | `backend/.env` (gitignored) |

Everything under `data/` except `inbox/` is derived and rebuildable. The
database is a single file — copy it to back up your study history.

---

## If something looks wrong

**Feed is empty or thin.** Check the corpus first:
`curl -s localhost:8000/api/agent/index/status`. Cards can only exist where
source material does.

**Ingest seems stuck.** Vision transcription is rate-limited to ~10 requests
per minute, so a page every six seconds is normal, not a hang. Watch
`data/overnight.log` or the transcript cache:
`find data/transcripts -name '*.md' | wc -l`.

**Quota exhausted.** `DailyQuotaExceeded` stops the run cleanly. Resume the
next day, or raise `GEMINI_MAX_REQUESTS_PER_DAY` in `.env` if your key is on
a paid tier.
