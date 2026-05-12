from __future__ import annotations

import unittest

from student_planner.domain.electives import (
    DEFAULT_ECTS_BY_ELECTIVE_CATEGORY,
    DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY,
    ElectiveCategory,
    ElectiveIntent,
    coerce_elective_category,
)
from student_planner.domain.models import RequirementType


class ElectiveDomainTests(unittest.TestCase):
    def test_category_aliases_and_ordering(self) -> None:
        self.assertEqual(coerce_elective_category("technical"), ElectiveCategory.TECHNICAL)
        self.assertEqual(coerce_elective_category("restricted_elective_pool"), ElectiveCategory.RESTRICTED)
        self.assertEqual(coerce_elective_category("non technical elective"), ElectiveCategory.NONTECHNICAL)
        self.assertEqual(coerce_elective_category("free-elective"), ElectiveCategory.FREE)

        self.assertGreater(
            DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY[ElectiveCategory.TECHNICAL],
            DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY[ElectiveCategory.RESTRICTED],
        )
        self.assertGreater(
            DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY[ElectiveCategory.RESTRICTED],
            DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY[ElectiveCategory.NONTECHNICAL],
        )
        self.assertGreater(
            DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY[ElectiveCategory.NONTECHNICAL],
            DIFFICULTY_RANK_BY_ELECTIVE_CATEGORY[ElectiveCategory.FREE],
        )

    def test_default_ects_assumptions(self) -> None:
        self.assertEqual(DEFAULT_ECTS_BY_ELECTIVE_CATEGORY[ElectiveCategory.TECHNICAL], 6.5)
        self.assertEqual(DEFAULT_ECTS_BY_ELECTIVE_CATEGORY[ElectiveCategory.RESTRICTED], 6.0)
        self.assertEqual(DEFAULT_ECTS_BY_ELECTIVE_CATEGORY[ElectiveCategory.NONTECHNICAL], 5.5)
        self.assertEqual(DEFAULT_ECTS_BY_ELECTIVE_CATEGORY[ElectiveCategory.FREE], 5.0)

    def test_elective_intent_normalizes_optional_course_code(self) -> None:
        intent = ElectiveIntent(category="te", course_code="ceng495")

        self.assertEqual(intent.category, ElectiveCategory.TECHNICAL)
        self.assertEqual(intent.course_code, "CENG 495")
        self.assertTrue(intent.has_explicit_course)
        self.assertFalse(intent.requires_explicit_course_selection)
        self.assertEqual(intent.default_ects, 6.5)
        self.assertEqual(intent.difficulty_rank, 4)
        self.assertEqual(intent.requirement_type, RequirementType.TECHNICAL_ELECTIVE_POOL)

    def test_elective_intent_without_course_remains_valid_placeholder(self) -> None:
        intent = ElectiveIntent(category="free_elective")

        self.assertEqual(intent.placeholder_code, "FREE_ELECTIVE")
        self.assertFalse(intent.has_explicit_course)
        self.assertTrue(intent.requires_explicit_course_selection)
        self.assertEqual(intent.default_ects, 5.0)

    def test_invalid_category_and_count_raise(self) -> None:
        with self.assertRaises(ValueError):
            ElectiveIntent(category="studio_elective")
        with self.assertRaises(ValueError):
            ElectiveIntent(category="free_elective", requested_count=0)


if __name__ == "__main__":
    unittest.main()
