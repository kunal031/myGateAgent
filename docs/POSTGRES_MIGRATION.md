# Postgres + pgvector Migration

Moving from SQLite + `.npy` vectors to PostgreSQL with pgvector.

---

## Why

| | SQLite today | Postgres + pgvector |
|---|---|---|
| Vectors at full scale | 347 MB **resident in the app** | on disk, HNSW indexed |
| Search (28k chunks) | 5.5 ms brute force | ~1–2 ms indexed |
| Concurrent writers | one, with WAL and a 30s busy timeout | native |
| Ops cost | none | a daemon to run and back up |

The deciding factor is **memory**. Search speed is already fine; holding
347 MB of float32 in the API process is not, and it grows with every book.
Postgres keeps vectors out of process.

Postgres 18 is already running locally with other databases, so the daemon
cost is close to zero here.

---

## Target schema

```
  gatemaster (database)
     │
     ├── syllabus       subjects, chapters, syllabus_topics,
     │                  subtopics, syllabus_concepts
     │
     ├── content        feed_cards, questions
     │
     ├── sources        sources, source_chunks
     │                  └── embedding vector(3072)   ← pgvector column
     │
     └── progress       attempts, mistake_registry, card_views,
                        exam_sessions, exam_items
```

Vectors live **on the chunk row** rather than in a parallel file, so a chunk
and its embedding can never drift apart — a failure mode the `.npy` store
had to guard against explicitly.

The schema removes that risk only once every writer uses it. The indexer
kept writing to `.npy` and setting `is_embedded` long after the column
existed, so 10,763 chunks were flagged embedded with no vector and semantic
search silently served the 2,590 rows copied during the migration. Two
lessons, both now enforced in `index.py`: a writer must branch on
`IS_SQLITE` like the read path does, and resume state must be derived from
the vector itself, never from a boolean that can outlive it.

---

## Index choice

```
  CREATE INDEX ON source_chunks
    USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

HNSW over IVFFlat: it needs no training pass, handles incremental inserts
well (chunks arrive continuously from ingestion), and its recall at these
defaults is high enough that the hybrid keyword half covers the rest.

**Dimension limit, resolved**: `vector` columns cannot be HNSW-indexed above
2,000 dimensions, and our embeddings are 3,072 — verified against pgvector
0.8.7, which rejects the index outright.

`halfvec` lifts that limit to 4,000, so the column is `halfvec(3072)`:

```
  CREATE INDEX ON source_chunks
    USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

Measured cost of half precision on 5,000 random 3,072-dim vectors: **top-10
overlap 10/10** against float32, at half the storage. Full dimensionality is
kept, no Matryoshka truncation needed, and the index works.

---

## Plan

```
  1  schema        create tables in Postgres, mirroring SQLAlchemy models
  2  dual-write    config switch: DATABASE_URL picks sqlite or postgres
  3  copy          migrate rows table by table, verify counts
  4  vectors       load .npy into source_chunks.embedding
  5  retrieval     swap VectorStore for a pgvector query
  6  verify        same queries, both backends, compare results
  7  cut over      DATABASE_URL points at Postgres; SQLite file kept as backup
```

Steps 1–4 are reversible. Step 7 is a config change, not a code change,
which keeps a rollback cheap.

**Status (2026-10-09)**: steps 1–7 complete against local Postgres. All
13,353 chunks carry a `halfvec(3072)` embedding, HNSW and GIN indexes are
in place, and retrieval runs through `pg_search`. The SQLite file remains as
a pre-ingestion backup and is deliberately stale at 2,590 chunks — it is no
longer a fallback, so do not reason about corpus size from it. Aiven is
likewise still at the 2,590-row snapshot; re-syncing it needs
`migrate_to_postgres` to read from local Postgres rather than SQLite.

---

## What changes in code

| File | Change |
|---|---|
| `core/config.py` | `DATABASE_URL` accepts a postgres DSN |
| `core/database.py` | drop the SQLite-specific PRAGMAs when not SQLite |
| `models/sources.py` | `embedding` column, `HALFVEC(3072)` |
| `services/retrieval/vector_store.py` | replaced by a pgvector query |
| `services/retrieval/keyword.py` | FTS5 → Postgres `tsvector` |
| `requirements.txt` | `psycopg[binary]`, `pgvector` |

The hybrid fusion, grading and generation layers are untouched: they take
`Match` objects and do not care where those came from.

---

## Keyword search

SQLite FTS5 has no direct Postgres equivalent, so the keyword half moves to
`tsvector` with `ts_rank_cd`. Behaviour differs slightly — Postgres stems by
dictionary rather than Porter-by-default — so the fusion weights are worth
re-checking on the same test queries after the move.

---

## Risk

**The main one**: a half-finished migration where some data is in SQLite and
some in Postgres. Mitigated by migrating whole tables with a count check
after each, and keeping the SQLite file untouched until cut-over succeeds.

**Second**: Postgres is now a dependency for the app to start at all, where
SQLite needed nothing. Acceptable here since the daemon already runs, but it
is a real change to the project's setup story and the runbook must say so.
