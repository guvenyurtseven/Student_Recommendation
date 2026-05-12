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
from student_planner.services.engineering_practice_rules import (
    augment_prerequisite_edges_by_course,
    engineering_practice_chains,
)
from student_planner.services.prerequisite_evaluator import PrerequisiteEdge


class EngineeringPracticeRulesTests(unittest.TestCase):
    def test_detects_practice_chain_from_summer_practice_requirements(self) -> None:
        chains = engineering_practice_chains(curriculum_fixture())

        self.assertEqual(len(chains), 1)
        self.assertEqual(chains[0].practice_300_code, "CENG 300")
        self.assertEqual(chains[0].practice_400_code, "CENG 400")

    def test_adds_ohs_to_300_and_300_to_400_edges(self) -> None:
        edges = augment_prerequisite_edges_by_course({}, curriculum_fixture())

        self.assertEqual(edges["CENG 300"][0].prerequisite_course_code, "OHS 301")
        self.assertEqual(edges["CENG 300"][0].course_code, "CENG 300")
        self.assertEqual(edges["CENG 400"][0].prerequisite_course_code, "CENG 300")
        self.assertEqual(edges["CENG 400"][0].course_code, "CENG 400")

    def test_adds_required_practice_rule_to_every_existing_alternative_set(self) -> None:
        edges = augment_prerequisite_edges_by_course(
            {
                "CENG 400": (
                    PrerequisiteEdge("CENG 280", "CENG 400", set_no="1"),
                    PrerequisiteEdge("CENG 290", "CENG 400", set_no="2"),
                )
            },
            curriculum_fixture(),
        )

        practice_edges = tuple(
            edge
            for edge in edges["CENG 400"]
            if edge.prerequisite_course_code == "CENG 300"
        )
        self.assertEqual({edge.set_no for edge in practice_edges}, {"1", "2"})

    def test_does_not_add_rules_for_non_engineering_curriculum(self) -> None:
        curriculum = curriculum_fixture(program_abbr="STAT", faculty="Arts and Sciences")

        edges = augment_prerequisite_edges_by_course({}, curriculum)

        self.assertEqual(edges, {})


def curriculum_fixture(program_abbr: str = "CENG", faculty: str = "Engineering") -> CurriculumSnapshot:
    return CurriculumSnapshot(
        program=Program(
            abbr=program_abbr,
            catalog_program_id="571",
            name_en="Computer Engineering",
            name_tr="Bilgisayar Muhendisligi",
            faculty=faculty,
        ),
        version_id=1,
        version_label="latest",
        is_latest=True,
        review_status=ReviewStatus.SCRAPED,
        requirements=(
            requirement(1, RequirementType.REQUIRED_COURSE, "OHS 301", "OHS", 301),
            requirement(2, RequirementType.SUMMER_PRACTICE, "CENG 300", "CENG", 300),
            requirement(3, RequirementType.SUMMER_PRACTICE, "CENG 400", "CENG", 400),
        ),
    )


def requirement(
    requirement_id: int,
    requirement_type: RequirementType,
    display_code: str,
    subject_code: str,
    course_number: int,
) -> CurriculumRequirementRecord:
    return CurriculumRequirementRecord(
        id=requirement_id,
        requirement_type=requirement_type,
        label=display_code,
        course_count_min=1,
        credits_min=0,
        ects_min=2 if display_code == "OHS 301" else 5,
        options=(
            CurriculumRequirementOption(
                id=requirement_id,
                course=Course(
                    numeric_code=None,
                    subject_code=subject_code,
                    course_number=course_number,
                    display_code=display_code,
                    title_en=display_code,
                ),
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
