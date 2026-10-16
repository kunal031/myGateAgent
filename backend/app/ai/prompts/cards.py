"""Prompts for generating feed cards, grounded in retrieved source text."""

SYSTEM = """You write revision cards for a GATE CSE aspirant targeting a top rank.

The single hard rule: every statement must be supported by the reference
material given to you. You are rewriting and clarifying what the sources say,
never adding knowledge from elsewhere. If the material does not support a
card, say so rather than inventing one.

Write densely. The reader is preparing for a competitive exam, not browsing.
Use LaTeX ($...$ inline, $$...$$ display) for all mathematics."""

BASIC_TEMPLATE = """Subject: {subject}
Topic: {topic}
Concept: {concept}

Reference material:
---
{context}
---

Write {count} BASIC cards introducing this concept to someone meeting it for
the first time. Definitions, intuition, notation, and the prerequisite ideas
needed before anything advanced. No exam traps yet.

Return JSON only:
{{
  "cards": [
    {{
      "card_type": "CONCEPT",
      "title": "Short, specific title",
      "content": "The explanation. Markdown and LaTeX allowed.",
      "takeaway": "One line the student should remember.",
      "sequence": 1,
      "source_number": 1,
      "supported_by": "A short quote from the reference material above that
                       supports this card."
    }}
  ]
}}

card_type is CONCEPT or FORMULA for BASIC cards.
source_number is the number of the single [Source N] block you relied on most.
If the reference material cannot support {count} cards, return fewer.
If it supports none, return {{"cards": []}}."""

ADVANCED_TEMPLATE = """Subject: {subject}
Topic: {topic}
Concept: {concept}

Reference material:
---
{context}
---

Write {count} ADVANCED cards for a student who already knows the basics of
this concept. Focus on what GATE actually tests and where candidates lose
marks: traps, edge cases, commonly confused pairs, derivations worth
memorising, and shortcuts that save exam time.

Return JSON only:
{{
  "cards": [
    {{
      "card_type": "TRAP",
      "title": "Short, specific title",
      "content": "The explanation. Markdown and LaTeX allowed.",
      "takeaway": "One line the student should remember.",
      "sequence": 1,
      "source_number": 1,
      "supported_by": "A short quote from the reference material above that
                       supports this card."
    }}
  ]
}}

card_type is TRAP, FORMULA, CONCEPT or SHORTCUT. source_number is the number
of the single [Source N] block you relied on most.

These cards exist for the student to NOT lose marks. A card that merely
restates a definition is worthless here -- that is what BASIC mode is for.
Every ADVANCED card must answer one of:
  - What does a candidate get WRONG here, and why? (TRAP)
  - What is the exact formula or condition, with its edge cases? (FORMULA)
  - How do I answer this faster under time pressure? (SHORTCUT)
  - Which two similar things are confused, and how do they differ? (TRAP)

Write at least half as TRAP or SHORTCUT where the material allows.
If the reference material cannot support {count} cards, return fewer.
If it supports none, return {{"cards": []}}."""
