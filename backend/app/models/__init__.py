"""Import every model module so all tables register on one metadata.

Several models carry foreign keys across modules (Question.concept_id,
Source.subject_id, ExamItem.question_id). SQLAlchemy resolves those targets
by table name at flush time, so a module importing only part of the schema
hits NoReferencedTableError. Importing the package guarantees the whole set
is present, whichever model a caller actually needs.
"""

from . import models  # noqa: F401  (base tables first)
from . import assistant, concepts, exams, rotation, sources, syllabus  # noqa: F401

__all__ = ["models", "concepts", "exams", "sources", "syllabus", "assistant", "rotation"]
