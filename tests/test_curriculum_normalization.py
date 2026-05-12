from __future__ import annotations

import unittest

from student_planner.domain.models import (
    Course,
    CurriculumRequirementOption,
    CurriculumRequirementRecord,
    CurriculumSnapshot,
    Program,
    RequirementType,
    ReviewStatus,
)
from student_planner.services.curriculum_normalization import normalize_curriculum_for_planning


class CurriculumNormalizationTests(unittest.TestCase):
    def test_engineering_turkish_choices_are_reduced_to_303_and_304(self) -> None:
        curriculum = CurriculumSnapshot(
            program=Program(
                abbr="CENG",
                catalog_program_id="571",
                name_en="Computer Engineering",
                name_tr="Bilgisayar Muhendisligi",
                faculty="Engineering",
            ),
            version_id=1,
            version_label="latest",
            is_latest=True,
            review_status=ReviewStatus.SCRAPED,
            requirements=(
                choice_requirement(1, ("TURK 105", "TURK 201", "TURK 303")),
                choice_requirement(2, ("TURK 106", "TURK 202", "TURK 304")),
            ),
        )

        normalized = normalize_curriculum_for_planning(curriculum)

        self.assertEqual(normalized.requirements[0].label, "TURK 303")
        self.assertEqual(normalized.requirements[0].requirement_type, RequirementType.REQUIRED_COURSE)
        self.assertEqual(normalized.requirements[0].option_course_codes, ("TURK 303",))
        self.assertEqual(normalized.requirements[0].recommended_term, "Fall")
        self.assertEqual(normalized.requirements[1].label, "TURK 304")
        self.assertEqual(normalized.requirements[1].option_course_codes, ("TURK 304",))
        self.assertEqual(normalized.requirements[1].recommended_term, "Spring")

    def test_engineering_history_choices_are_reduced_to_2201_and_2202(self) -> None:
        curriculum = CurriculumSnapshot(
            program=Program(
                abbr="CENG",
                catalog_program_id="571",
                name_en="Computer Engineering",
                name_tr="Bilgisayar Muhendisligi",
                faculty="Engineering",
            ),
            version_id=1,
            version_label="latest",
            is_latest=True,
            review_status=ReviewStatus.SCRAPED,
            requirements=(
                choice_requirement(1, ("HIST 2201", "HIST 2205")),
                choice_requirement(2, ("HIST 2202", "HIST 2206")),
            ),
        )

        normalized = normalize_curriculum_for_planning(curriculum)

        self.assertEqual(normalized.requirements[0].label, "HIST 2201")
        self.assertEqual(normalized.requirements[0].requirement_type, RequirementType.REQUIRED_COURSE)
        self.assertEqual(normalized.requirements[0].option_course_codes, ("HIST 2201",))
        self.assertEqual(normalized.requirements[0].recommended_term, "Fall")
        self.assertEqual(normalized.requirements[1].label, "HIST 2202")
        self.assertEqual(normalized.requirements[1].option_course_codes, ("HIST 2202",))
        self.assertEqual(normalized.requirements[1].recommended_term, "Spring")

    def test_non_engineering_curriculum_is_left_unchanged(self) -> None:
        curriculum = CurriculumSnapshot(
            program=Program(
                abbr="STAT",
                catalog_program_id="240",
                name_en="Statistics",
                name_tr="Statistics",
                faculty="Arts and Sciences",
            ),
            version_id=1,
            version_label="latest",
            is_latest=True,
            review_status=ReviewStatus.SCRAPED,
            requirements=(choice_requirement(1, ("TURK 105", "TURK 201", "TURK 303")),),
        )

        normalized = normalize_curriculum_for_planning(curriculum)

        self.assertIs(normalized, curriculum)


def choice_requirement(requirement_id: int, course_codes: tuple[str, ...]) -> CurriculumRequirementRecord:
    return CurriculumRequirementRecord(
        id=requirement_id,
        requirement_type=RequirementType.COURSE_CHOICE,
        label="Any 1 of the following set ..",
        recommended_year=3,
        recommended_term="Fifth Semester",
        course_count_min=1,
        options=tuple(
            CurriculumRequirementOption(
                id=requirement_id * 10 + index,
                course=Course(
                    numeric_code=None,
                    subject_code=course_code.split()[0],
                    course_number=int(course_code.split()[1]),
                    display_code=course_code,
                    title_en=course_code,
                ),
            )
            for index, course_code in enumerate(course_codes)
        ),
    )


if __name__ == "__main__":
    unittest.main()
