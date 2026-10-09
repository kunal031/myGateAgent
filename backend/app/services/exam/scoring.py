"""Official GATE marking, shared by quiz drills and mock tests."""

from ...models.models import Question


def score_item(question: Question, answer: str) -> tuple[bool, float]:
    """Return (is_correct, marks) for one answer.

    MCQ carries negative marking; MSQ is all-or-nothing with no penalty;
    NAT is checked against the published tolerance range.
    """
    answer = answer.strip()
    if not answer:
        return False, 0.0

    if question.question_type == "MCQ":
        correct = answer.upper() == question.correct_answer.strip().upper()
        return correct, float(question.marks) if correct else -float(question.negative_marks)

    if question.question_type == "MSQ":
        expected = sorted(t.strip().upper()
                          for t in question.correct_answer.split(",") if t.strip())
        given = sorted(t.strip().upper() for t in answer.split(",") if t.strip())
        correct = expected == given
        return correct, float(question.marks) if correct else 0.0

    # NAT
    try:
        value = float(answer)
    except ValueError:
        return False, 0.0

    if question.nat_min is not None and question.nat_max is not None:
        correct = question.nat_min <= value <= question.nat_max
    else:
        try:
            correct = value == float(question.correct_answer)
        except ValueError:
            correct = False
    return correct, float(question.marks) if correct else 0.0
