# Source Material

The source files are **not in git** (1.1 GB). This records where each set came
from so the corpus can be rebuilt on a clean machine, and so every generated
card can credit its real author.

Everything lands in `backend/data/inbox/`, which is the permanent drop folder.
Re-running ingestion after adding files is safe: content hashing makes a repeat
drop a no-op.

---

## Inbox layout

```
backend/data/inbox/
├── notes/
│   ├── github-priyanshu/     12 subject PDFs   (1,062 pages)
│   ├── handwritten-air50/    14 PDFs             (613 pages)
│   └── karan-suthar/         65 files            (24 concept images + notes)
├── books/
│   └── Karumanchi DSA                            (828 pages)
└── pyq/
    ├── topicwise/            GATE Wallah         (606 pages)
    └── papers/               18 files: 9 papers + 9 answer keys
```

---

## 1. GitHub — Priyanshu (GATE 2024 AIR 379, GATE 2023 AIR 384)

- **Origin:** https://github.com/Priyanshuu-2109/GATE-CSE-notes
- **Rebuild:** `git clone --depth 1 <url>`, then copy the PDFs into
  `inbox/notes/github-priyanshu/` (strip the `!` from filenames)
- **Content:** all 12 core subjects — Algorithms, COA (x2), Compiler Design,
  Computer Networks, Data Structures, DBMS, Digital Logic, Discrete Mathematics,
  Engineering Mathematics, Operating System, Theory of Computation
- **Credit:** "Priyanshu, GATE 2024 AIR 379" (the author watermarks each page)
- **Extraction:** **vision required.** 5 files are pure scans; the other 7 carry
  a text layer that is bad OCR — e.g. `"In Place algonithm"`, `"Merge sot"`,
  `"soting agonitam"`. Using that text directly would poison the feed, so all
  1,062 pages go through vision transcription.

## 2. Handwritten notes — AIR < 50 topper

- **Origin:** Google Drive, downloaded by `app/services/download_notes.py`
  (file IDs are in that module)
- **Content:** 12 subject notebooks plus two standouts:
  - `Silly_Mistakes_Log.pdf` — the author's own error log. **Highest-value file
    in the corpus:** real mistakes that cost real marks, which is exactly what
    TRAP cards should be built from. Verified examples: *"asked for how much %
    decreased, answered how much % increased"*; *"BW = 64 kbps (10³) given,
    still used K = 2¹⁰"*; *"created two copies of PAS for P and C but shared
    global variable"*.
  - `Preparation_Strategy.pdf` — the only file here with a clean text layer.
- **Extraction:** vision for 607 pages; 6 pages direct.

## 3. Karan Suthar notes + concept images

- **Origin:** https://drive.google.com/drive/folders/11LtgEN_iSkrIKNSgwyvETaxxeON4zokq
- **Verified:** the local copy is a superset of this folder, so no re-download
  is needed.
- **Content worth noting:** 24 single-image comparison tables under
  `Important to GATE CSE/` — DecidableUndecidableTable, Moore vs Mealy, RISC vs
  CISC, Port Numbers, Types of Parsers, Scheduling Algorithms, TCP/UDP. Dense,
  high-yield, and ideal for direct card generation via vision.
- **Excluded:** 37 files under `Test Marks/` and `Gate Result 2026.png`. These
  are mock-test score screenshots belonging to someone else — no study content,
  so indexing them would waste quota and dilute retrieval. The classifier marks
  them `EXCLUDED`.

## 4. Books

- `Data Structures and Algorithms — Narasimha Karumanchi` (828 pages)
- **Extraction:** mixed; treated as vision to be safe.

## 5. Previous year papers and keys

- **Topicwise:** `GATE Wallah Topicwise PYQ — CS/IT (Physics Wallah)`, 606 pages,
  clean text layer. **The single most useful source for question generation,**
  because questions are already grouped by topic.
- **Papers:** 2019, 2020, 2021 (Set-1, Set-2), 2022, 2023, 2025, 2026 (Set-1,
  Set-2) — each with its official answer key.
  - Note: 2024 is absent. Worth adding.
- **Extraction:** mostly direct (free). Only 2020, 2021 Set-1 and the two large
  books need vision.

---

## Extraction cost summary

Measured by sampling 5 pages per file and discarding watermark-only text:

| | pages |
|---|---|
| Need vision transcription | **3,211** |
| Extractable directly (free) | 343 |

At the free-tier cap of ~1,400 requests/day, a full vision pass is **~2.3 days**
of background ingestion. It is resumable and cached per page, so it can run in
chunks and never re-transcribes a page it has already done.

**Suggested ingestion order** (value per token spent):
1. `Silly_Mistakes_Log.pdf` — 14 pages, highest value, validates the pipeline
2. `Important to GATE CSE/` concept images — 24 images, dense comparison tables
3. GATE Wallah topicwise PYQ — direct extraction, drives question generation
4. PYQ papers + answer keys — direct extraction
5. Handwritten subject notes — 607 pages, bulk vision
6. GitHub subject notes — 1,062 pages, bulk vision
7. Karumanchi — 828 pages, lowest priority (textbook, least GATE-specific)
