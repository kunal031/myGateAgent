"""Prompts for extracting and generating quiz questions."""

EXTRACT_SYSTEM = """You extract real GATE exam questions from a PYQ compilation
into structured data.

Rules:
- Extract only questions actually present in the text. Never invent one.
- Keep the question wording as printed, including all numbers and symbols.
- Use LaTeX ($...$ inline, $$...$$ display) for mathematics.
- A question whose options or answer are cut off by the page break is
  incomplete: skip it rather than guessing the missing part.
- The marks tag [GATE-YYYY: 1M] or [: 2M] gives both year and marks."""

EXTRACT_TEMPLATE = """Subject: {subject}

Text from a GATE PYQ compilation:
---
{context}
---

Extract every complete question. Return JSON only:
{{
  "questions": [
    {{
      "question_type": "MCQ",
      "content": "The question text, with LaTeX for any mathematics.",
      "options": [
        {{"id": "A", "text": "..."}},
        {{"id": "B", "text": "..."}},
        {{"id": "C", "text": "..."}},
        {{"id": "D", "text": "..."}}
      ],
      "correct_answer": "A",
      "nat_min": null,
      "nat_max": null,
      "marks": 1,
      "exam_year": 2023,
      "explanation": "Why the answer is correct, from the text if given.",
      "topic_hint": "the chapter or topic heading this sits under"
    }}
  ]
}}

question_type is MCQ (one correct), MSQ (one or more correct, answer like
"A,C") or NAT (numerical, no options, set nat_min and nat_max to the accepted
range and leave options empty).

If the answer key is not in the text, set correct_answer to "" and the
question is skipped. Return {{"questions": []}} if none are complete."""


GENERATE_SYSTEM = """You write GATE CSE practice questions from a student's own
study material.

Every question must be answerable from the reference material given. Do not
introduce facts it does not contain. Match the style of a real GATE paper:
precise, unambiguous, and solvable in two to three minutes.

Use LaTeX for all mathematics."""

GENERATE_TEMPLATE = """Subject: {subject}
Topic: {topic}
Concept: {concept}

Reference material:
---
{context}
---

Write {count} GATE-style questions on this concept.

Return JSON only:
{{
  "questions": [
    {{
      "question_type": "MCQ",
      "content": "The question.",
      "options": [{{"id": "A", "text": "..."}}],
      "correct_answer": "A",
      "nat_min": null,
      "nat_max": null,
      "marks": 2,
      "explanation": "Full working, not just the answer.",
      "supported_by": "A short quote from the reference material."
    }}
  ]
}}

Mix the types: MCQ, MSQ and NAT, as a real paper does. Prefer questions that
test the trap or edge case rather than recall of a definition.
If the material cannot support {count} questions, return fewer."""
