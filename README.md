# 🎯 GateMaster — GATE CSE 2027 (Mission 80+ Marks / AIR < 100)

> A personalized, high-yield preparation platform built specifically for working professionals (9–7 office schedule) to maximize active recall, eliminate traps, and conquer the GATE CSE exam.

---

## ⚡ Quickstart

Launch both the **FastAPI Backend** and the **Next.js Frontend** with a single command:

```bash
./start.sh
```

- **Frontend Application**: [http://localhost:3000](http://localhost:3000)
- **Interactive Backend Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🧠 System Architecture

GateMaster connects active test-taking directly to a prioritized revision feed:

```
┌─────────────────────────────────────────────────────────────┐
│                      Next.js Frontend                       │
│  [Feed]       [Quiz Drill]    [Mock Test]   [AI Agent]   [Analytics]
└──────┬──────────────┬───────────────────────────┬───────────┘
       │              │                           │
       ▼              ▼                           ▼
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                       │
│  • Spaced Recall Weighting Matrix (Boosts failed topics)    │
│  • Official GATE Scoring Engine (MCQ -0.33/-0.66, MSQ, NAT) │
│  • SQLite Telemetry Database (Attempts & Mistake Registry)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Modules Built in Phase 1

1. **Revision Feed (`/feed`)**:
   - Micro-learning flashcards: **Key Formulas**, **Trap Alerts**, **Core Concepts**, and **Rank Shortcuts**.
   - High-yield **KaTeX** math formulas and code rendering.
   - **Remedial Boosting**: Any question failed in the Quiz or Test automatically boosts that topic's cards to the top of the feed until resolved.
   - Filterable by Subject and Card Type.

2. **Quiz Drills (`/quiz`)**:
   - Full support for **MCQ** (Single Choice with negative marking), **MSQ** (Multiple Select, all-or-nothing, 0 negative marks), and **NAT** (Numerical Answer with tolerance).
   - Real-time question timer and immediate step-by-step KaTeX explanations.
   - Direct integration with the **Mistake Registry**.

3. **AIR < 100 Analytics (`/analytics`)**:
   - Total questions drilled, global accuracy %, and net marks accrued.
   - Active unresolved mistakes counter.
   - Subject-by-subject error heatmap with historical GATE weightage indicators.

4. **Exam Engine Simulator (`/test`)**:
   - Configurable test modes: Full 3-Hour / 65-Question mock, Subject sprints, and Custom mixed drills.

5. **AI Professor & RAG Specialist (`/agent`)**:
   - Conversational assistant indexed on standard reference textbooks (Cormen, Galvin, Tanenbaum, Ullman) and 35-year PYQ corpus.

---

## 📚 Complete GATE CSE 2027 Syllabus Coverage

All 11–12 core syllabus subjects are modeled with their topic hierarchies and historical mark distributions:
- **General Aptitude** (~15 Marks)
- **Engineering Mathematics & Discrete Math** (~13 Marks)
- **Programming & Data Structures** (~9 Marks)
- **Operating Systems** (~9 Marks)
- **Algorithms** (~8 Marks)
- **Theory of Computation** (~8 Marks)
- **Computer Organization & Architecture** (~8 Marks)
- **Computer Networks** (~8 Marks)
- **Databases (DBMS)** (~7 Marks)
- **Digital Logic** (~5 Marks)
- **Compiler Design** (~4 Marks)

---

## 🛠️ Next Roadmap

- **Phase 2**: Full 3-hour exam testing UI with GATE Virtual Calculator, full 65-question palette (Answered, Marked for Review, Visited), and sectional timing analytics.
- **Phase 3**: RAG integration with local ChromaDB vector store for standard textbooks and on-demand AI question/trap generation.
