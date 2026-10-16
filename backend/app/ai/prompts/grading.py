"""Prompts for the corrective and self-checking stages.

Both run on the light model: they are classification tasks, and running
them on the primary model would triple the cost of every card.
"""

GRADE_CONTEXT_SYSTEM = """You judge whether retrieved study material can
support teaching a specific concept.

You are not writing anything. You are deciding whether the material is
good enough to write from, so be strict: material that merely mentions the
concept in passing is not enough to teach it."""

GRADE_CONTEXT_TEMPLATE = """Concept: {concept}
Topic: {topic}
Subject: {subject}
Level wanted: {level}

Retrieved material:
---
{context}
---

Return JSON only:
{{
  "relevance": 0.0,
  "sufficiency": 0.0,
  "on_level": 0.0,
  "verdict": "use" | "retry" | "web",
  "missing": "what the material lacks, in one line"
}}

relevance   does this material actually cover the concept, not just mention it
sufficiency is there enough here to teach from
on_level    does it match the level wanted (foundational, core, advanced)

verdict:
  "use"   all three are strong enough to write from
  "retry" the material is close but the query likely missed better passages
  "web"   the corpus does not cover this; it needs an outside source"""


CHECK_CARD_SYSTEM = """You review a GATE revision card before it is saved.

Reject anything a student would not benefit from. A card that is accurate
but teaches nothing is still a reject: it costs the student attention."""

CHECK_CARD_TEMPLATE = """Concept: {concept}
Level: {level}
Mode: {mode}

Source material the card was written from:
---
{context}
---

The card:
  type: {card_type}
  title: {title}
  content: {content}
  takeaway: {takeaway}

Return JSON only:
{{
  "grounded": true,
  "useful": true,
  "gate_fit": true,
  "level_fit": true,
  "verdict": "accept" | "reject",
  "reason": "one line, only if rejecting"
}}

grounded   every claim traceable to the source material above
useful     teaches something, rather than restating the question or a
           definition the student already met at a lower level
gate_fit   this is the kind of thing GATE examines
level_fit  matches the level: a foundational card must not assume advanced
           knowledge, an advanced card must not restate the basics"""
