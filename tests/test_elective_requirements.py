from __future__ import annotations

import unittest

from student_planner.domain.electives import ElectiveCategory, ElectiveIntent
from student_planner.domain.models import RequirementType
from student_planner.domain.planning import (
    CompletedCourseAttempt,
    PlanningGoal,
    RequirementProgress,
    RequirementProgressStatus,
    StudentPlanningInput,
)
from student_planner.services.curriculum_progress import CurriculumProgressResult
from student_planner.services.elective_requirements import ElectiveRequirementPlanner


class ElectiveRequirementPlannerTests(unittest.TestCase):
    def test_matches_requested_intents_to_remaining_slots(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(),
            goal=PlanningGoal("20252"),
            elective_intents=(
                ElectiveIntent("technical_elective"),
                ElectiveIntent("free_elective", requested_count=2),
            ),
        )

        result = ElectiveRequirementPlanner().build(
            planning_input,
            progress_result(
                requirements=(
                    elective_requirement("Technical Elective", RequirementType.TECHNICAL_ELECTIVE_POOL, count=2),
                    elective_requirement("Free Elective", RequirementType.FREE_ELECTIVE_POOL, count=1),
                )
            ),
        )

        by_category = {plan.category: plan for plan in result.category_plans}
        self.assertEqual(by_category[ElectiveCategory.TECHNICAL].remaining_slots, 2)
        self.assertEqual(by_category[ElectiveCategory.TECHNICAL].requested_count, 1)
        self.assertEqual(by_category[ElectiveCategory.TECHNICAL].matched_count, 1)
        self.assertEqual(by_category[ElectiveCategory.TECHNICAL].unplanned_count, 1)
        self.assertEqual(by_category[ElectiveCategory.FREE].remaining_slots, 1)
        self.assertEqual(by_category[ElectiveCategory.FREE].requested_count, 2)
        self.assertEqual(by_category[ElectiveCategory.FREE].extra_count, 1)
        self.assertIn("elective_intent_exceeds_curriculum_slots", {warning.code for warning in result.warnings})

    def test_warns_when_requested_category_has_no_remaining_slot(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(),
            goal=PlanningGoal("20252"),
            elective_intents=(ElectiveIntent("restricted_elective"),),
        )

        result = ElectiveRequirementPlanner().build(planning_input, progress_result(requirements=()))

        self.assertEqual(result.category_plans[0].remaining_slots, 0)
        self.assertEqual(result.category_plans[0].extra_count, 1)
        self.assertEqual(result.warnings[0].code, "elective_intent_without_curriculum_slot")

    def test_explicit_elective_courses_are_flagged_for_category_review(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(),
            goal=PlanningGoal("20252"),
            elective_intents=(ElectiveIntent("technical_elective", course_code="ceng495"),),
        )

        result = ElectiveRequirementPlanner().build(
            planning_input,
            progress_result(
                requirements=(
                    elective_requirement("Technical Elective", RequirementType.TECHNICAL_ELECTIVE_POOL, count=1),
                )
            ),
        )

        self.assertIn("explicit_elective_category_requires_review", {warning.code for warning in result.warnings})

    def test_completed_transcript_electives_reduce_remaining_slots(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(
                CompletedCourseAttempt("PSYC 100", "CC", credits=3),
                CompletedCourseAttempt("ECON 210", "BA", credits=3),
                CompletedCourseAttempt("MATH 119", "AA", credits=4),
            ),
            goal=PlanningGoal("20252"),
        )

        result = ElectiveRequirementPlanner().build(
            planning_input,
            progress_result(
                requirements=(
                    regular_requirement("MATH 119"),
                    elective_requirement("Non-Technical Elective", RequirementType.NONTECHNICAL_ELECTIVE_POOL, count=3),
                    elective_requirement("Free Elective", RequirementType.FREE_ELECTIVE_POOL, count=1),
                )
            ),
        )

        by_category = {plan.category: plan for plan in result.category_plans}
        self.assertEqual(by_category[ElectiveCategory.NONTECHNICAL].completed_count, 2)
        self.assertEqual(by_category[ElectiveCategory.NONTECHNICAL].remaining_slots, 1)
        self.assertIsNone(result.easy_priority_category)

    def test_easy_priority_category_prefers_nontechnical_before_free(self) -> None:
        planning_input = StudentPlanningInput(
            program_abbr="CENG",
            completed_courses=(),
            goal=PlanningGoal("20252"),
        )

        result = ElectiveRequirementPlanner().build(
            planning_input,
            progress_result(
                requirements=(
                    elective_requirement("Non-Technical Elective", RequirementType.NONTECHNICAL_ELECTIVE_POOL, count=3),
                    elective_requirement("Free Elective", RequirementType.FREE_ELECTIVE_POOL, count=1),
                )
            ),
        )

        self.assertEqual(result.easy_priority_category, ElectiveCategory.NONTECHNICAL)


def progress_result(requirements: tuple[RequirementProgress, ...]) -> CurriculumProgressResult:
    return CurriculumProgressResult(
        program_abbr="CENG",
        curriculum_version_label="latest",
        requirements=requirements,
    )


def elective_requirement(
    label: str,
    requirement_type: RequirementType,
    count: int,
) -> RequirementProgress:
    return RequirementProgress(
        requirement_label=label,
        requirement_type=requirement_type,
        status=RequirementProgressStatus.NEEDS_REVIEW,
        course_count_min=count,
    )


def regular_requirement(course_code: str) -> RequirementProgress:
    return RequirementProgress(
        requirement_label=course_code,
        requirement_type=RequirementType.REQUIRED_COURSE,
        status=RequirementProgressStatus.SATISFIED,
        completed_course_codes=(course_code,),
        option_course_codes=(course_code,),
        course_count_min=1,
    )


if __name__ == "__main__":
    unittest.main()
