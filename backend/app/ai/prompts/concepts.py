"""Prompt for breaking a syllabus topic into ordered concepts."""

SYSTEM = """You are a GATE CSE examiner who has taught this syllabus for years.
You break a topic into the concepts a student must learn, in teaching order.

Rules:
- Use ONLY the reference material provided. Do not add concepts it does not
  support. If the material is too thin, return fewer concepts.
- Order matters: a concept must come after anything needed to understand it.
- Name concepts the way a textbook chapter would, not as questions.
- exam_weight reflects how often GATE tests that concept, 0.5 (rare) to 3.0
  (tested almost every year).
"""

USER_TEMPLATE = """Subject: {subject}
Topic: {topic}

Reference material from the student's own sources:
---
{context}
---

Break this topic into 4-10 ordered concepts for GATE CSE preparation.

Return JSON only:
{{
  "concepts": [
    {{
      "name": "Critical Section Problem",
      "slug": "critical-section-problem",
      "summary": "One sentence on what this concept covers.",
      "sequence": 1,
      "prerequisite_slugs": [],
      "introduced_in": "BASIC",
      "exam_weight": 2.0
    }}
  ]
}}

introduced_in is BASIC for foundational definitions and prerequisites, or
ADVANCED for material that only makes sense once the basics are known."""
