"""Exam patterns: how a paper is composed.

The full pattern mirrors the real GATE CS paper -- 65 questions for 100
marks, with General Aptitude fixed at 15 marks -- so a full mock scores on
the same scale as the exam.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SectionSpec:
    """How many questions of each mark value come from a subject group."""
    subject_slugs: tuple[str, ...]
    one_mark: int
    two_mark: int

    @property
    def marks(self) -> int:
        return self.one_mark + 2 * self.two_mark


@dataclass(frozen=True)
class ExamPattern:
    key: str
    name: str
    duration_minutes: int
    sections: tuple[SectionSpec, ...] = field(default_factory=tuple)

    @property
    def total_questions(self) -> int:
        return sum(s.one_mark + s.two_mark for s in self.sections)

    @property
    def total_marks(self) -> int:
        return sum(s.marks for s in self.sections)


# Real GATE CS: 10 GA questions worth 15 marks, 55 technical worth 85.
FULL_GATE = ExamPattern(
    key="full",
    name="Full GATE Mock (65Q / 100M / 3h)",
    duration_minutes=180,
    sections=(
        SectionSpec(("general-aptitude",), one_mark=5, two_mark=5),
        SectionSpec(
            (
                "engineering-mathematics", "digital-logic",
                "computer-organization-architecture", "programming-data-structures",
                "algorithms", "theory-of-computation", "compiler-design",
                "operating-systems", "databases", "computer-networks",
            ),
            one_mark=25, two_mark=30,
        ),
    ),
)

PRESETS: dict[str, ExamPattern] = {p.key: p for p in (FULL_GATE,)}


def subject_sprint(subject_slug: str, questions: int, minutes: int) -> ExamPattern:
    """A single-subject paper, split so roughly half the marks come from 2M."""
    two_mark = questions // 2
    return ExamPattern(
        key="subject",
        name=f"Subject Sprint ({questions}Q / {minutes}m)",
        duration_minutes=minutes,
        sections=(SectionSpec((subject_slug,), questions - two_mark, two_mark),),
    )


def custom_mix(subject_slugs: list[str], questions: int, minutes: int) -> ExamPattern:
    """A mixed paper across chosen subjects."""
    two_mark = questions // 2
    return ExamPattern(
        key="custom",
        name=f"Custom Drill ({questions}Q / {minutes}m)",
        duration_minutes=minutes,
        sections=(SectionSpec(tuple(subject_slugs), questions - two_mark, two_mark),),
    )
